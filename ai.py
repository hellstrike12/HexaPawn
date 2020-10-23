import bus
import os
from validators import Validator
from objects import Pawn
from graphviz import Graph
from uuid import uuid1
from random import choice
from PyPDF2 import PdfFileReader, PdfFileWriter


class Node():
    # Constructor
    def __init__(self, node_id, children, weight=0):
        self.node_id = node_id  # Movecode for that node
        self.children = children  # Nodes generated by this node


class Ai():
    # Constructor
    def __init__(self, mode='exclusive'):
        self.pawns = [
            Pawn("black", "a3", silent=True),
            Pawn("black", "b3", silent=True),
            Pawn("black", "c3", silent=True),
            Pawn("white", "a1", silent=True),
            Pawn("white", "b1", silent=True),
            Pawn("white", "c1", silent=True)
        ]
        self.judge = Validator(self.pawns)
        self.nodes = []  # Node tree
        self.stack = []  # Move call stack
        self.generation = 0  # Generation counter

        # Decision making
        self.wins = 0
        self.losses = 0
        self.last_move = ''

        # Modes
        # inclusive = Copies leaves that lead to victory
        # exclusive = Removes leaves that lead to defeat
        # both = inclusive + exclusive
        self.mode = mode  # Describes how the algorithm learns

        entry_moves = ['a2', 'b2', 'c2']
        # Test all entry moves and create all possible nodes
        for move in entry_moves:
            self.nodes.append(self.__make_nodes([move]))

        # Initial state snapshot graph
        self.__snapshot()

    # Generates nodes (neurons)
    def __make_nodes(self, movecode):
        # Reset the judge, so it can make
        # all moves from the beginning
        self.judge.reset(True)

        # Execute the moves
        for code in movecode:
            self.judge.check(code, silent=True)

        # Results for this state
        children = []

        # Check if the moves resulted in victory
        self.judge.victory_validator(True)
        if (self.judge.white_wins == 1):
            self.judge.white_wins = 0
            return Node(movecode[::-1][0], children=[])
        elif (self.judge.black_wins == 1):
            self.judge.black_wins = 0
            return Node(movecode[::-1][0], children=[])

        # Sort pawns by color
        blacks = []
        whites = []
        for pawn in self.judge.group:
            if (pawn.color == 'black'):
                blacks.append(pawn)
            else:
                whites.append(pawn)

        col_dict = {
            "a": ["b"],
            "b": ["a", "c"],
            "c": ["b"]
        }

        # Check for all possible movements
        for pawn in (whites if (len(movecode) % 2 == 0) else blacks):
            # Check for movements
            if (self.judge.move_check(pawn.id)[0] == True):
                children.append(
                    f'{pawn.id[0]}{int(pawn.id[1]) + (-1 if (pawn.color == "black") else 1)}')

            # Check for captures
            for col in col_dict[pawn.id[0]]:
                if (self.judge.capture_check(pawn.id, f'{col}{int(pawn.id[1]) + (-1 if (pawn.color == "black") else 1)}')[0] == True):
                    children.append(
                        f'{pawn.id[0]}x{col}{int(pawn.id[1]) + (-1 if (pawn.color == "black") else 1)}')

        for node in children:
            idx = children.index(node)
            test = movecode.copy()
            test.append(node)
            children[idx] = self.__make_nodes(test)

        return Node(movecode[::-1][0], children)

    # Access the corresponding node
    def step(self, white_move):
        self.stack.append(white_move)
        self.__victory_check()

        if (self.stack != []):
            node = self.__traceroute(self.stack)
            move = choice(node.children)
            self.stack.append(move.node_id)
            bus.judge.check(move.node_id)
            self.__victory_check()

    def __victory_check(self):
        # Get last black decision node (parent) and the child
        if (len(self.stack) > 1):
            if (len(self.stack) % 2 == 0):
                parent = self.__traceroute(self.stack[0:len(self.stack)-1])
                node = self.__traceroute(self.stack)
            else:
                parent = self.__traceroute(self.stack[0:len(self.stack)-2])
                node = self.__traceroute(self.stack[0:len(self.stack)-1])

        # Compare the new win state
        if (bus.judge.black_wins > self.wins):
            # The last move resulted in a win
            # copy that child if mode is inclusive or both
            print('[VICTORY] Blacks wins')
            if (self.mode in ['inclusive', 'both']):
                parent.children.append(node)
                self.generation += 1
                self.__snapshot()

            # Clear the move stack, since the judge reseted
            self.stack = []
            self.wins += 1

        elif (bus.judge.white_wins > self.losses):
            # The last move resulted in a lose
            # remove that child if mode is exclusive or both
            print('[VICTORY] White wins')
            if (self.mode in ['exclusive', 'both']):
                parent.children.remove(node)
                self.generation += 1
                self.__snapshot()

            # Clear the move stack, since the judge reseted
            self.stack = []
            self.losses += 1

    # Advances in the tree
    def __traceroute(self, movecodes):
        actual_node = None
        for move in movecodes:
            scope = (actual_node.children if (
                actual_node != None) else self.nodes)
            for node in scope:
                if (node.node_id == move):
                    actual_node = node

        return actual_node

    # Plot a graph containing all neurons at current state
    def __snapshot(self):
        # Initializing
        dot = Graph(
            comment='HexaPawn',
            filename=os.path.join('plots', 'HexaPawn.gv')
        )
        dot.attr(
            center='true',
            rankdir='LR',
            ranksep='5.0 equally',
            label=f'Generation {self.generation}',
            fontsize='40'
        )

        # Create entry layer
        layers = {}
        links = []

        # Populate layers
        depth = 0
        parent_nodes = self.nodes
        while True:
            test = [True if (node.children != [])
                    else False for node in parent_nodes]
            if (test.count(True) > 0):
                # Create layer nodes
                layer = self.__create_layer(parent_nodes)

                # Store layer
                layers.update({str(depth): layer})

                # Repeat the process using this layer's children
                next_nodes = []
                link = []
                for node in parent_nodes:
                    for child in node.children:
                        next_nodes.append(child)
                        link.append([node.node_id, child.node_id])

                links.append(link)

                parent_nodes = next_nodes
                depth += 1
            else:
                break

        # Create the links
        for x in range(6):
            self.__linker(layers, links, x, dot)

        # Finally, render the graph
        dot.render()

        # Rename the output according to the current generation
        os.rename(os.path.join('plots', 'HexaPawn.gv.pdf'),
                  os.path.join('plots', f'{self.generation}.pdf'))

    # Merge all snapshots
    def plot(self):
        pdf_writer = PdfFileWriter()

        for x in range(self.generation + 1):
            pdf_reader = PdfFileReader(os.path.join('plots', f'{x}.pdf'))
            for page in range(pdf_reader.getNumPages()):
                # Add each page to the writer object
                pdf_writer.addPage(pdf_reader.getPage(page))

        # Write out the merged PDF
        with open(os.path.join('plots', 'generations.pdf'), 'wb') as out:
            pdf_writer.write(out)

        # Delete generation snapshot
        # (since it was added to the main file
        # we don't need it anymore)
        for x in range(self.generation + 1):
            os.remove(os.path.join('plots', f'{x}.pdf'))

    def __create_layer(self, parent_nodes):
        layer = {}
        for node in parent_nodes:
            node_id = str(uuid1())
            layer.update({node.node_id: node_id})

        return layer

    def __linker(self, layers, links, depth, dot):
        # Fetch layers
        try:
            layer = layers[f'{depth}']
            sublayer = layers[f'{depth + 1}']
        except:
            return None

        # Define node colors based on actual depth
        if (depth % 2 == 0):
            # Fill color, text color
            layer_style = ['white', 'black']
            sublayer_style = ['black', 'white']
        else:
            layer_style = ['black', 'white']
            sublayer_style = ['white', 'black']

        link = links[depth]
        for lk in link:
            dot.node(
                name = layer[lk[0]], 
                label = lk[0],
                shape = 'circle',
                width = '1',
                height='1',
                style = 'filled', 
                fillcolor = layer_style[0],
                fontcolor = layer_style[1]
            )
            tail = layer[lk[0]]

            dot.node(
                name = sublayer[lk[1]], 
                label = lk[1],
                shape = 'circle',
                width = '1',
                height='1',
                style = 'filled', 
                fillcolor = sublayer_style[0],
                fontcolor = sublayer_style[1]
            )
            head = sublayer[lk[1]]

            dot.edge(tail, head)


def autoplay():
    # Column capture resolver
    col_dict = {
        "a": ["b"],
        "b": ["a", "c"],
        "c": ["b"]
    }

    # Sort white pawns
    whites = []
    for pawn in bus.judge.group:
        if (pawn.color == 'white'):
            whites.append(pawn)

    # Fetch all white possible moves
    moves = []
    for pawn in whites:
        # Check for movements
        if (bus.judge.move_check(pawn.id)[0] == True):
            moves.append(f'{pawn.id[0]}{int(pawn.id[1]) + 1}')

        # Check for captures
        for col in col_dict[pawn.id[0]]:
            if (bus.judge.capture_check(pawn.id, f'{col}{int(pawn.id[1]) + 1}')[0] == True):
                moves.append(f'{pawn.id[0]}x{col}{int(pawn.id[1]) + 1}')

    # Pick a random move and execute
    move = choice(moves)
    bus.judge.check(move)

    # Notify AI
    bus.ai.step(move)
