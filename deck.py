# Define class Deck that has a list of cards and methods to shuffle, draw, etc.

import random


class Deck:
    def __init__(self, cards):
        self.cards = cards
    
    def shuffle(self):
        random.shuffle(self.cards)
    
    def draw(self):
        return self.cards.pop()

    def __str__(self):
        return str(self.cards)

    def get_card(self, name):
        for card in self.cards:
            if card.name == name:
                # Remove the card from the deck and return it
                self.cards.remove(card)
                return card
        return None

    def count_cards(self, name):
        count = 0
        for card in self.cards:
            if card.name == name:
                count += 1
        return count
