
# CardList extends the list class to add a few methods for dealing with
# a list of cards.
import json
import pickle
import random
import time
from typing import List

MAXINT = 2**31 - 1

class Cards(list):
    def __init__(self, cards=None, randseed=None):
        super().__init__()
        self.randseed = randseed
        # If cards is a string, then it is a list of cards to parse and add to the deck
        if isinstance(cards, str):
            for line in cards.split('\n'):
                # Lines are in the format of "quantity cardname"
                if line:
                    quantity, cardname = line.split(' ', 1)
                    self.add_cards_by_name(cardname, quantity)
        elif isinstance(cards, List):
            self.extend(cards)

    def add_cards_by_name(self, cardname, quantity=1):
        found_subclass = None
        # Find subclasses of Card that have a name that matches the card name and add each one to the deck
        for subclass in Card.__subclasses__():
            if subclass.name == cardname:
                found_subclass = subclass
                break
        if not found_subclass:
            print ("Warning: Card not found: " + cardname)
        else:
            for i in range(int(quantity)):
                self.append(found_subclass())

    def shuffle(self):
        # Shuffle the deck with a fixed seed
        if not self.randseed is None:
            random.seed(self.randseed)
        random.shuffle(self)

    def draw(self, quant=1):
        if quant == 1:
            return self.pop()
        else:
            return [self.pop() for i in range(quant)]

    def find_and_remove(self, name, quantity=1) -> List['Card']:
        # Return up to X instances of cards with the given name.
        # If there are not enough cards, return what you can.
        retval = []

        for card in list(self):
            if card.name == name:
                retval.append(card)
                self.remove(card)
                if len(retval) == quantity:
                    break

        self.shuffle()

        return retval

    def find(self, name, quantity=1) -> List['Card']:
        # Return up to X instances of cards with the given name.
        # If there are not enough cards, return what you can.
        retval = []

        for card in list(self):
            if card.name == name:
                retval.append(card)
                if len(retval) == quantity:
                    break

        return retval

    def reveal_cards_until(self, name):
        # Reveal cards until the given card is found.
        # Return the list of revealed cards.
        revealed_cards = []
        revealed_card = None
        while True:
            if len(self) == 0:
                break
            card = self.draw()
            revealed_cards.append(card)
            if card.name == name:
                revealed_card = card
                break
        return revealed_cards, revealed_card

    def reveal_cards_until_not(self, name):
        # Reveal cards until something OTHER than the given card is found.
        # Return the list of revealed cards.
        revealed_cards = []
        revealed_card = None
        while True:
            if len(self) == 0:
                break
            card = self.draw()
            revealed_cards.append(card)
            if not card.name == name:
                revealed_card = card
                break
        return revealed_cards, revealed_card

    def count_cards(self, name, in_top=0) -> int:
        count = 0
        peek_cnt = 0
        for card in reversed(self):
            if card.name == name:
                count += 1
            peek_cnt += 1
            if in_top == peek_cnt:
                break
        return count

    def put_on_bottom(self, card):
        # If card is a list, put each card on the bottom of the deck
        if isinstance(card, list):
            for c in card:
                self.put_on_bottom(c)
        else:
            self.insert(0, card)

    def get_card(self, card) -> 'Card':
        if isinstance(card, int):
            return self[card]
        if isinstance(card, str):
            for c in self:
                if c.name == card:
                    return c
            return None
        else:
            return card


class Player:
    land_drops:int = 0
    lands:int = 0
    mana_pool:int = 0
    current_turn:int = 0
    creature_died_this_turn:bool = False
    opponent_lifetotal:int = 20
    is_pruned:bool = False # Marks a player state as pruned, meaning that it should not be evaluated for exhaustive search anymore.
    pickledump = None
    can_cast_wurm_now:bool = False

    def __init__(self, decklist, randseed=None):
        if randseed is None:
            randseed = time.time()
        self.randseed = randseed
        self.deck:Cards = Cards(decklist, randseed)
        self.hand:Cards = Cards()
        self.graveyard:Cards = Cards()
        self.table:Cards = Cards()
        self.exile:Cards = Cards()
        self.log:List[str] = [""]
        self.childstates:List['Player'] = []
        # If we don't have any Panglacial Wurms in the deck, we can shortcut some costly checks.
        self.panglacial_in_deck:bool = self.deck.count_cards('Panglacial Wurm') > 0

    def draw(self, quantity=1):
        self.log.append(f" Draw {quantity} card(s)")
        for i in range(quantity):
            self.hand.append(self.deck.draw())

    def can_play(self, card) -> bool:
        card = self.hand.get_card(card)
        if card is None:
            return False

        if card in self.hand:
            return card.can_play(self)
        return False

    def play(self, card):
        card = self.hand.get_card(card)

        if card in self.hand:
            if not card.can_play(self):
                print(f' ERROR: Cannot play {card}')
                raise Exception(f' ERROR: Cannot play {card}')
            else:
                self.log.append(f" Play: {card}")
                self.hand.remove(card)
                self.mana_pool -= card.cost
                card.play(self)

    def can_alt_play(self, card) -> bool:
        card = self.hand.get_card(card)
        if card is None:
            return False

        if card in self.hand:
            return card.can_alt_play(self)
        return False

    def alt_play(self, card):
        card = self.hand.get_card(card)

        if card in self.hand:
            if not card.can_alt_play(self):
                print(f' ERROR: Cannot alt play {card}')
                raise Exception(f' ERROR: Cannot alt play {card}')
            else:
                self.log.append(f" Alt play: {card}")
                self.hand.remove(card)
                self.mana_pool -= card.alt_cost
                card.alt_play(self)

    def can_activate(self, card) -> bool:
        if isinstance(card, Card):
            return card in self.table and card.can_activate(self)
        else:
            for tablecard in self.table:
                if tablecard.name == card and tablecard.can_activate(self):
                    return True

        return False

    def activate(self, card):
        card = self.table.get_card(card)

        if card in self.table:
            if not card.can_activate(self):
                # Throw exception
                print(f' ERROR: Cannot activate {card}')
                raise Exception(f' ERROR: Cannot activate {card}')
            else:
                self.log.append(f" Activate: {card}")
                self.mana_pool -= card.activation_cost
                card.activate(self)

    def panglacial_potential(self, additional_cost) -> bool:
        if not self.panglacial_in_deck:
            return False
        # Check if we have a Panglacial Wurm in our deck, and have enough mana to cast it.
        return (self.mana_pool >= PanglacialWurm.cost + additional_cost
            and self.deck.count("Panglacial Wurm") > 0)

    def check_panglacial(self):
        if self.panglacial_potential(0):
            self.can_cast_wurm_now = True

    def has_spellmastery(self):
        # If there are two or more instant and sorcery cards in your graveyard, you have spellmastery
        return self.graveyard.count_cards('Instant') + self.graveyard.count_cards('Sorcery') >= 2

    def start_turn(self):
        # Increment turn count
        self.current_turn += 1
        self.log.append(f"Beginning turn {self.current_turn}: " + self.short_str())
        # If it's the first turn, shuffle up and draw 7 cards
        if self.current_turn == 1:
            self.deck.shuffle()
            self.draw(7)
        # Untap all mana
        self.mana_pool = self.lands
        # Reset flags and counts
        self.creature_died_this_turn = False
        self.land_drops = 1
        self.can_cast_wurm_now = False
        # Upkeep for permanents on table and cards in hand
        for card in self.table:
            card.do_upkeep(self)
        for card in self.hand:
            card.do_upkeep(self)
        for card in self.exile:
            card.do_upkeep(self)

        # Draw a card for turn if it's not the first turn
        if self.current_turn > 1:
            self.draw()

    def check_win(self) -> bool:
        return self.opponent_lifetotal <= 0

    def step_next_actions(self) -> List['Player']:
        if self.is_pruned:
            return []

        if len(self.childstates) == 0:
            next_states = []

            # Return a list of game states that are possible from the current state
            # This is used to generate a tree of possible game states
            if self.check_win():
                self.log.append("!!!You are a win!!!")
                self.childstates = [self]
                return self.childstates

            # Check if we can cast a Panglacial Wurm
            #  Note that we're technically checking this after the resolution of whatever spell
            #   did the searching, but because the check that set this flag looked at the amount
            #   of mana that was available at the time of the search, we can cast the Panglacial
            #   Wurm now without any loss of gameplay integrity.
            if self.can_cast_wurm_now:
                # Make a copy of the current state
                new_state = self.copy()
                # Retrieve the wurm from within the deck
                wurm = new_state.deck.find_and_remove("Panglacial Wurm", 1)
                # Add the wurm to our hand
                new_state.hand.append(wurm)
                # Cast the wurm
                new_state.play(wurm[0])
                new_state.can_cast_wurm_now = False
                # Add the new state to the list of child states
                next_states.append(new_state)

                # If we don't take advantage of it now, we've lost the opportunity for later.
                self.can_cast_wurm_now = False

            # No-brainer decisions:
            #  * If we have a land in our hand, play it
            #  * If we can cast Land Grant for free, then do so
            #  * If we can attack with a creature, then do so
            #  Otherwise, loop through all other cards in hand and activations (if any) and evaluate them.

            # Land drops take priority, always do those first.
            # If we can drop a land, and we have 1 or more lands in hand, then play them.
            if self.land_drops > 0 and self.hand.count_cards('Forest') > 0:
                copy = self.copy()
                copy_lands = copy.hand.find('Forest', copy.land_drops)
                for copy_land in copy_lands:
                    copy.play(copy_land)

                next_states.append(copy)
            # Otherwise, if we can play Land Grant for its alternate cost, do that.
            elif self.can_alt_play('Land Grant'):
                copy = self.copy()
                copy.alt_play('Land Grant')
                next_states.append(copy)
            # Check to see if we can attack with a creature
             # Can we attack with Chancellor?
            elif self.can_activate('Chancellor of the Tangle'):
                # Find the first copy of Chancellor in our new table that can be activated.
                copy = self.copy()
                for copy_card in copy.table:
                    if copy_card.name == 'Chancellor of the Tangle' and copy_card.can_activate(copy):
                        copy.activate(copy_card)
                        next_states.append(copy)
                        break
                if not copy in next_states:
                    raise Exception("ERROR: Chancellor of the Tangle should be able to attack, but can't.")
             # Can we attack with Panglacial Wurm?
            elif self.panglacial_in_deck and self.can_activate('Panglacial Wurm'):
                copy = self.copy()
                copy.activate('Panglacial Wurm')
                next_states.append(copy)
            # NOTE: If one wants to make saccing Steve a no-brainer, then uncomment the following lines.
            # Leaving this commented will increase branching permutations, but may be worth it
            #  for selectively saving the activation for things like Caravan Vigil or Panglacial Wurm.
            #elif self.can_activate('Sakura-Tribe Elder'):
            #    copy = self.copy()
            #    copy.activate('Sakura-Tribe Elder')
            #    next_states.append(copy)
            else:
                # Get a list of every unique card name in the hand
                unique_hand_cards = []
                for card in self.hand:
                    if card not in unique_hand_cards:
                        unique_hand_cards.append(card)

                # For every unique card, if we can play that card, then play it.  Don't branch more than once for each card name.
                for card in unique_hand_cards:
                    can_altplay = self.can_alt_play(card)

                    # Only play it for regular if the card doesn't prefer to be alt played
                    if self.can_play(card) and not (can_altplay and card.prefer_alt):
                        copy = self.copy()
                        copy.play(card.name)
                        next_states.append(copy)
                    if can_altplay:
                        copy = self.copy()
                        copy.alt_play(card.name)
                        next_states.append(copy)

                # However, for cards already on the field, we can activate multiples of the same card

                # Attempt to activate every card on the table
                for card_idx, card in enumerate(self.table):
                    if self.can_activate(card):
                        copy = self.copy()
                        copy_card = copy.table[card_idx]
                        copy.activate(copy_card)
                        next_states.append(copy)

                # Always consider the option of just passing the turn.
                # Note that this will increase branching permutations and may be of questionable value.
                # TODO: Evaluate the baseline to see if this measurably increases win rate or not.
                # Just because we CAN do something on our turn, is there ever any benefit to NOT doing it on our turn?
                # Or should we attempt to always use every resource available to us?
                #copy = self.copy()
                #copy.start_turn()
                #next_states.append(copy)

            self.childstates = next_states

        # If after all that, child states is still empty, then go to the next turn.
        if len(self.childstates) == 0:
            copy = self.copy()
            copy.start_turn()
            self.childstates.append(copy)

        return self.childstates


    def copy(self) -> 'Player':
        # Serialize self into a string
        ser = self.serialize()
        # Deserialize the string into a new Player object
        copy = Player.deserialize(ser)
        return copy

    def serialize(self):
        # Cache the pickle dump so that we don't do this any more frequently than we have to.
        if self.pickledump is None:
            # Serialize self by using pickle
            pickledump = pickle.dumps(self)
            # Cache the result for later in case we need to make multiple copies (quite likely)
            self.pickledump = pickledump
        return self.pickledump

    @staticmethod
    def deserialize(ser) -> 'Player':
        # Deserialize the pickle into a new Player object
        return pickle.loads(ser)

    def dumplog(self):
        print('\n'.join(self.log))

    def __str__(self) -> str:
        # Print out the player's current state
        s = f"Turn [{self.current_turn}] - Opponent Life: {self.opponent_lifetotal}\n"
        s += f" {self.deck.count_cards('Forest')} Forests in library\n"
        s += f" Lands: {self.mana_pool} / {self.lands}  ({self.land_drops} drops avail.)\n"
        s += f" Hand: {len(self.hand)} cards\n"
        # Display the hand sorted alphabetically
        for card in sorted(self.hand, key=lambda x: x.name):
            s += f"  {card}\n"
        s += f" Table: {len(self.table)} cards\n"
        for card in sorted(self.table, key=lambda x: x.name):
            s += f"  {card}\n"
        s += f" Graveyard: {len(self.graveyard)} cards\n"
        for card in sorted(self.graveyard, key=lambda x: x.name):
            s += f"  {card}\n"
        s += f" Library: {len(self.deck)} cards\n"
        s += f" Exile: {len(self.exile)} cards\n"

        return s


    def short_str(self) -> str:
        # Print out the player's current state in a very short format
        # Current turn, number of lands left in our deck, number of cards in hand, mana in our pool, lands on the field, opponent's life total, and the last log entry
        return f"{self.current_turn})  LID: {self.deck.count_cards('Forest')}  H: {len(self.hand)}  Mana: {self.mana_pool}/{self.lands} [{self.hand.count_cards('Forest')}]  OLife: {self.opponent_lifetotal} '{self.log[-1]}'"

    # Methods to support testing
    def debug_force_get_card_in_hand(self, card_name) -> 'Card':
        # Ensure that the player has the given card in their hand. If they don't, then retrieve on from the deck.
        if not self.hand.count_cards(card_name) > 0:
            card = self.deck.find_and_remove(card_name)[0]
            self.hand.append(card)
        return self.hand.find(card_name)[0]

# Define generic Card class that has a cost, name, and ability function
class Card:
    name:str = 'card'
    cost:int = 0
    alt_cost:int = MAXINT
    activation_cost:int = MAXINT
    cardtype:str = 'None'
    prefer_alt:bool = False # If the alternate cost is available, don't evaluate the regular cost.  This is useful for cards like Caravan Vigil and Land Grant.

    def __str__(self):
        return self.name

    def long_str(self, controller: Player):
        return self.name + f" [{self.cost}]   Can play: {self.can_play(controller)} / {self.can_alt_play(controller)}   Can activate: {self.can_activate(controller)}"

    def play(self, controller: Player):
        self.resolve(controller)

    def resolve(self, controller: Player):
        # If it's a permanent, put it on the table
        if self.is_permanent():
            controller.table.append(self)
        else:
            # Otherwise it goes into the graveyard
            controller.graveyard.append(self)

    def can_play(self, controller: Player) -> bool:
        return self.cost <= controller.mana_pool

    def alt_play(self, controller: Player):
        self.resolve(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return self.alt_cost <= controller.mana_pool

    def activate(self, controller: Player):
        pass

    def can_activate(self, controller: Player) -> bool:
        return self.activation_cost <= controller.mana_pool

    def is_permanent(self) -> bool:
        return not (self.cardtype == 'Instant' or self.cardtype == 'Sorcery')

    def do_upkeep(self, controller: Player):
        pass

# Forest is a card that costs 0 and has an ability that increases a player's land count by 1
# ASSUMPTION: We always tap every land for mana immediately.
#  Adding a land to the battlefield untapped is to increase the controller's land count
#   (how much mana is available after untap) and also increases the amount available in a
#   player's mana pool.
#  Note that this causes some tricky assumptions when it comes to Wild Growth (which only
#   immediately adds a mana if there was an untapped forest when it was played), but we are
#   able to work around it alright I think.
class Forest (Card):
    name = 'Forest'
    cost:int = 0
    cardtype = 'Land'

    def can_play(self, controller: Player) -> bool:
        return controller.land_drops > 0

    def play(self, controller: Player):
        controller.lands += 1
        controller.mana_pool += 1 # Assume that every land is immediately tapped for mana when it's played.
        controller.land_drops -= 1
        super().play(controller)

# Lay of the Land is a card that costs 1 and has an ability that searches the deck for a land and puts it into the player's hand
class LayOfTheLand (Card):
    name = 'Lay of the Land'
    cost:int = 1
    cardtype = 'Sorcery'

    def __init__(self):
        self.mana_value = 1
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

# Caravan Vigil is a card that costs 1 and has an ability that says: Search your library for a basic land card, reveal it, put it into your hand, then shuffle your library. You may put that card onto the battlefield instead of putting it into your hand if a creature died this turn.
# NOTE: The morbid mode of the card is done as an alternate play, so that we can more easily track its effect on the game.
class CaravanVigil (Card):
    name = 'Caravan Vigil'
    cost:int = 1
    alt_cost:int = 1
    cardtype = 'Sorcery'
    prefer_alt = True

    def __init__(self):
        self.mana_value = 1
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.deck.count_cards('Forest') > 0 and controller.creature_died_this_turn

    def alt_play(self, controller: Player) -> bool:
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        # Add the land to the battlefield
        controller.table.extend(cards)
        controller.lands += len(cards)
        # The land comes into play untapped
        controller.mana_pool += len(cards)
        super().alt_play(controller)

# Sakura-Tribe Elder is a creature that costs 2 and has an ability that says: Sacrifice Sakura-Tribe Elder: Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.
class SakuraTribeElder (Card):
    name = 'Sakura-Tribe Elder'
    cost:int = 2
    cardtype = 'Creature'
    activation_cost:int = 0

    def can_activate(self, controller: Player) -> bool:
        return (self in controller.table
            and (
                controller.deck.count_cards('Forest') > 0
                or controller.panglacial_potential(self.activation_cost))
            )

    def activate(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        # Add a tapped forest
        controller.table.extend(cards)
        controller.lands += len(cards)
        # Destroy self
        if not self in controller.table:
            raise Exception("Sakura-Tribe Elder is not on the battlefield")
        controller.table.remove(self)
        controller.graveyard.append(self)
        # Mark that a creature died this turn
        controller.creature_died_this_turn = True

# Arboreal Grazer is a creature that costs 1 that says "When Arboreal Grazer enters the battlefield, you may put a land card from your hand onto the battlefield tapped."
class ArborealGrazer (Card):
    name = 'Arboreal Grazer'
    cost:int = 1
    cardtype = 'Creature'

    def play(self, controller: Player):
        super().play(controller)
        # Put a land into play tapped
        cards = controller.hand.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.table.extend(cards)
        controller.lands += len(cards)

    # Only let us play this card if we have at least 1 Forest in hand.
    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.hand.count_cards('Forest') > 0

# Reclaim the Wastes is a card that costs 1 and when played, searches the deck for a land and puts it into the player's hand.
#  It has an alternate cost of 4 that searches for 2 lands instead.
class ReclaimTheWastes (Card):
    name = 'Reclaim the Wastes'
    cost:int = 1
    alt_cost:int = 4
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

    def can_alt_play (self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.deck.count_cards('Forest') > 1

    def alt_play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 2)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().alt_play(controller)

# Land Grant is a card that costs 2 and has an ability that searches the deck for a land and puts it into the player's hand
# However, if the player has no lands in hand, it costs 0.
# Each mode is implemented as a separate cost.
class LandGrant(Card):
    name = 'Land Grant'
    cost:int = 2
    alt_cost:int = 0
    cardtype = 'Sorcery'
    prefer_alt = True

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return (super().can_alt_play(controller)
            and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.alt_cost))
            and controller.hand.count_cards('Forest') == 0)

    def alt_play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().alt_play(controller)

# Goblin Charbelcher is a card that costs 4. It has an Activation ability that costs 3, and when activated, removes cards from the top of the library until a land is reached.  It reduces the enemy life total by the number of cards revealed this way and puts them all onto the bottom of the library.
# NOTE: If we permit the game to activate Belcher prior to removing all lands from the deck, it will be possible to win much faster. HOWEVER, this is also "cheating" in that the game knows the contents of the deck and can therefore make a decision that the player cannot.
#  Therefore, we will (artificially) limit the game to optimize for the case where Belcher is activated after all lands have been removed from the deck.
# NOTE: This is in contrast to the decisions we have made in other places, such as Ancient Stirrings, that will only let us cast it if we have a "hit" in the top 5 cards of the deck. The alternative is to not implement Ancient Stirrings at all, but that's not great.
#  For now, just understand that the value of Belcher is artificially deflated (due to not being able to risk premature belching), and the value of Ancient Stirrings is artificially inflated (due to not being able to risk not finding a hit).
class GoblinCharbelcher(Card):
    name = 'Goblin Charbelcher'
    cost:int = 4
    activation_cost:int = 3
    cardtype = 'Artifact'

    def __init__(self):
        self.is_tapped = False

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    # NOTE: Should we allow the user to activate with forests still remaining in the deck?  It feels very shuffle-dependent, and I would like to optimize for the case where we can belcher the opponent out of the game guaranteed.
    def can_activate(self, controller: Player) -> bool:
        return (super().can_activate(controller)
            and not self.is_tapped
            and controller.deck.count_cards('Forest') == 0)

    def activate(self, controller: Player):
        self.is_tapped = True
        cards, revealed_card = controller.deck.reveal_cards_until('Forest')
        controller.opponent_lifetotal -= len(cards)
        controller.deck.put_on_bottom(cards)
        lands_in_deck = controller.deck.count_cards('Forest')
        controller.log.append(f'  Belcher with {lands_in_deck} lands in deck')

# Elvish Mystic is a card that costs 1 and has an ability that increases a player's mana pool by 1
#  NOTE: This is a bit of a hack, but when we play it we simply increase the player's land count by 1,
#   which means that the player will have extra mana in their mana pool starting *next* turn.
class ElvishMystic (Card):
    name = 'Elvish Mystic'
    cost:int = 1
    cardtype = 'Creature'

    def __init__(self):
        self.is_tapped = True
        pass

    def play(self, controller: Player):
        # Instead of activating to add mana to our mana pool, just treat it as a new land so we don't have as many branching permutations.
        controller.lands += 1
        super().play(controller)


# Llanowar Elves is a copy of Elvish Mystic with a different name
class LlanowarElves (Card):
    name = 'Llanowar Elves'
    cost:int = 1
    cardtype = 'Creature'

    def __init__(self):
        self.is_tapped = True
        pass

    def play(self, controller: Player):
        # Instead of activating to add mana to our mana pool, just treat it as a new land so we don't have as many branching permutations.
        controller.lands += 1
        super().play(controller)

# Rampant Growth is a card with an ability: Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.
class RampantGrowth(Card):
    name = 'Rampant Growth'
    cost:int = 2
    cardtype = 'Sorcery'

    def can_play(self, controller: Player) -> bool:
        # Don't play unless we have a land in the deck, or we have a potential to cast Panglacial Wurm
        return (super().can_play(controller)
            and (
                controller.deck.count_cards('Forest') > 0
                or controller.panglacial_potential(self.cost))
            )

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        # Add a tapped forest
        controller.lands += len(cards)
        controller.table.extend(cards)
        super().play(controller)

# Nissa's Pilgrimage is a card with the ability: Search your library for up to two basic Forest cards, reveal those cards, and put one onto the battlefield tapped and the rest into your hand. Then shuffle your library.  If there are two or more instant and/or sorcery cards in your graveyard, search your library for up to three basic Forest cards instead of two.
class NissasPilgrimage(Card):
    name = 'Nissa\'s Pilgrimage'
    cost:int = 3
    alt_cost:int = 3
    prefer_alt = True

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        search_count = 2

        cards = controller.deck.find_and_remove('Forest', search_count)
        # Put the first card onto the battlefield tapped
        if len(cards) > 0:
            card = cards.pop()
            controller.table.append(card)
            controller.lands += 1

        # Add the rest to the hand
        controller.hand.extend(cards)
        super().play(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.deck.count_cards('Forest') > 2 and controller.has_spellmastery()

    def alt_play(self, controller: Player):
        search_count = 3

        cards = controller.deck.find_and_remove('Forest', search_count)
        # Put the first card onto the battlefield tapped
        if len(cards) > 0:
            card = cards.pop()
            controller.table.append(card)
            controller.lands += 1

        # Add the rest to the hand
        controller.hand.extend(cards)
        super().alt_play(controller)

# Wall of Roots is a card that costs 2 and has an ability that increases a player's mana pool by 1
# NOTE: This is a bit of a hack.  For now we're going to treat this as a land enters untapped, but doesn't remove a Forest from the deck.
#  so we don't have to deal with the branching permutations of activating it.
# If the AI starts to over-value Wall of Roots, consider restoring the prior implementation (saved for reference)
class WallOfRoots (Card):
    name = 'Wall of Roots'
    cost:int = 2
    cardtype = 'Creature'

    def play(self, controller: Player):
        controller.lands += 1
        controller.mana_pool += 1
        super().play(controller)

"""
class WallOfRoots (Card):
    name = 'Wall of Roots'
    cost:int = 2
    cardtype = 'Creature'
    activation_cost:int = 0

    def __init__(self):
        self.is_tapped:bool = False

    def play(self, controller: Player):
        self.toughness = 5
        self.is_tapped = False # Start off untapped when played because it can activate on the first turn
        super().play(controller)

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    def can_activate(self, controller: Player) -> bool:
        return not self.is_tapped and self in controller.table

    def activate(self, controller: Player):
        controller.mana_pool += 1
        self.is_tapped = True
        self.toughness -= 1
        # If toughness is <= 0, destroy the card
        if self.toughness <= 0:
            controller.table.remove(self)
            controller.graveyard.append(self)
            # Mark that a creature died this turn
            controller.creature_died_this_turn = True
"""

# Explore is a card that costs 2 and has an ability that says: You may play an additional land this turn. Draw a card.
class Explore(Card):
    name = 'Explore'
    cost:int = 2
    cardtype = 'Sorcery'

    def play(self, controller: Player):
        controller.land_drops += 1
        controller.draw()
        super().play(controller)

# Chancellor of the Tangle costs 7 and has an ability that says: You may reveal this card from your opening hand. If you do, at the beginning of your first main phase, add 1 to your mana pool
class ChancellorOfTheTangle(Card):
    name = 'Chancellor of the Tangle'
    cost:int = 7
    cardtype = 'Creature'
    activation_cost:int = 0 # Costs nothing to attack

    def __init__(self):
        self.is_tapped:bool = False
        pass

    def play(self, controller: Player):
        self.is_tapped = True # Start off tapped to simulate summoning sickness
        super().play(controller)

    def do_upkeep(self, controller: Player):
        self.is_tapped = False
        # If the card is in the opening hand, add 1 to the mana pool
        if controller.hand.count(self) > 0:
            if controller.current_turn == 1:
                controller.log.append(f'  Chancellor of the Tangle adding 1 to mana pool')
                controller.mana_pool += 1

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped) and (self in controller.table)

    def activate(self, controller: Player):
        self.is_tapped = True
        controller.opponent_lifetotal -= 6
        if controller.opponent_lifetotal <= 0:
            controller.log.append(f'  Chancellor of the Tangle attacked for 6 and won the game')
        else:
            controller.log.append(f'  Chancellor of the Tangle attacked for 6')

# Wild Growth is an enchantment that costs 1 and has an ability that says: Whenever enchanted land is tapped for mana, its controller adds an additional mana
class WildGrowth(Card):
    name = 'Wild Growth'
    cost:int = 1
    cardtype = 'Enchantment'

    # Only allow this card to be played if the table contains a Forest
    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.table.count_cards('Forest') > 0

    def play(self, controller: Player):
        controller.lands += 1 # Simulate effect by just adding an additional land
        # If there is at least one unused mana when this is played, then add 1 to the mana pool, implying that we played this against an untapped land.
        #  Note: This isn't perfect, but it's probably good 'nuff.
        if controller.mana_pool > 0 and controller.lands > 0:
            controller.mana_pool += 1
        super().play(controller)

# Search for Tomorrow is a sorcery that costs 3 and says: Search your library for a basic land card, put it onto the battlefield, then shuffle. Suspend 2— (Rather than cast this card from your hand, you may pay  and exile it with two time counters on it. At the beginning of your upkeep, remove a time counter. When the last is removed, cast it without paying its mana cost.)
class SearchForTomorrow(Card):
    name = 'Search for Tomorrow'
    cost:int = 3
    alt_cost:int = 1
    cardtype = 'Sorcery'

    def __init__(self):
        self.time_counters = 0

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.table.extend(cards)
        controller.lands += 1
        controller.mana_pool += 1 # The land comes into play untapped, so immediately add it to the mana pool.
        super().play(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(0))

    def alt_play(self, controller: Player):
        self.time_counters = 2
        # Note: Don't call super().resolve() here because we don't want to put this card in the graveyard
        controller.exile.append(self)

    def do_upkeep(self, controller: Player):
        # If we are in the controller's exile zone, then remove a time counter
        if self in controller.exile:
            self.time_counters -= 1
            controller.log.append(f'  Suspend: Search for Tomorrow has {self.time_counters} time counters')
            # If the last time counter is removed, then cast the card
            if self.time_counters == 0:
                self.play(controller)

# Recross the Paths is a sorcery that costs 3 and says: Reveal cards from the top of your library until you reveal a land card. Put that card onto the battlefield and the rest on the bottom of your library in any order. Clash with an opponent. If you win, return Recross the Paths to its owner's hand.
class RecrossThePaths(Card):
    name = 'Recross the Paths'
    cost:int = 3
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def play(self, controller: Player):
        # Reveal cards from the top of the library until a land is found
        cards, land = controller.deck.reveal_cards_until('Forest')
        # If a land was found this way, then put it onto the battlefield untapped
        if land is not None:
            controller.table.append(land)
            controller.lands += 1
            controller.mana_pool += 1
            controller.log.append(f'  Recross the Paths: Found a land')
            cards.remove(land)
        else:
            controller.log.append(f'  Recross the Paths: No land found. Deck stacked')
        # Put the rest of the cards back on the bottom of the library
        # Sort the cards so that any Goblin Charbelchers are at the top, and any other cards at the bottom in an arbitrary order.
        remaining_cards = []
        for card in cards:
            if card.name == 'Goblin Charbelcher':
                controller.deck.put_on_bottom(card)
            else:
                remaining_cards.append(card)
        controller.deck.put_on_bottom(remaining_cards)
        # TODO: Clash with an opponent. If you win, return Recross the Paths to its owner's hand.
        # Pretend that we always win the clash.
        controller.hand.append(self)
        # TODO: Make this a random chance?

# Ancient Stirrings is a sorcery that costs 1 and says: Look at the top five cards of your library. You may reveal a colorless card from among them and put it into your hand. Then put the rest on the bottom of your library in any order.
class AncientStirrings(Card):
    name = 'Ancient Stirrings'
    cost:int = 1
    alt_cost:int = 1
    cardtype = 'Sorcery'

    def do_stirrings(self, controller: Player, target_type: str):
        # Look at the top five cards of your library
        cards = controller.deck.draw(5)
        # Reveal a colorless card from among them and put it into your hand
        found_card = None

        for card in cards:
            if card.cardtype == target_type:
                found_card = card

        if not found_card is None:
            cards.remove(found_card)
            controller.hand.append(found_card)

        # Put the rest on the bottom of your library in any order
        controller.deck.put_on_bottom(cards)

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.deck.count_cards('Goblin Charbelcher', in_top=5) > 0

    def play(self, controller: Player):
        self.do_stirrings(controller, 'Artifact')
        super().play(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.deck.count_cards('Forest', in_top=5) > 0

    def alt_play(self, controller: Player) -> bool:
        self.do_stirrings(controller, 'Land')
        super().alt_play(controller)

# Abundant Harvest is a sorcery that costs 1 that says: Choose land or nonland. Reveal cards from the top of your library until you reveal a card of the chosen kind. Put that card into your hand and the rest on the bottom of your library in a random order.
class AbundantHarvest(Card):
    name = 'Abundant Harvest'
    cost:int = 1
    alt_cost:int = 1
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def do_harvest(self, controller: Player, target_land: bool):
        # Reveal cards from the top of your library until you reveal a card of the chosen kind
        if target_land:
            cards, found_card = controller.deck.reveal_cards_until('Forest')
        else:
            cards, found_card = controller.deck.reveal_cards_until_not('Forest')

        # Put that card into your hand
        if found_card is not None:
            controller.hand.append(found_card)
            cards.remove(found_card)
        # Put the rest on the bottom of your library in a random order
        controller.deck.put_on_bottom(cards)

    # Play is for when you want to target a land
    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.deck.count_cards('Forest') > 0

    def play(self, controller: Player):
        # Land
        self.do_harvest(controller, True)
        super().play(controller)

    # Alt play is for when you want to target a nonland
    def alt_play(self, controller: Player) -> bool:
        # Nonland
        self.do_harvest(controller, False)
        super().alt_play(controller)

# Panglacial Wurm is a creature that costs 7 and says: Trample. While you're searching your library, you may cast Panglacial Wurm from your library.
class PanglacialWurm(Card):
    name = 'Panglacial Wurm'
    cost:int = 7
    activation_cost:int = 0 # Costs nothing to attack
    cardtype = 'Creature'

    def __init__(self):
        self.is_tapped:bool = False

    def play(self, controller: Player):
        self.is_tapped = True # Start off tapped to simulate summoning sickness
        super().play(controller)

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped) and (self in controller.table)

    def activate(self, controller: Player):
        self.is_tapped = True
        controller.opponent_lifetotal -= 9
        if controller.opponent_lifetotal <= 0:
            controller.log.append(f'  Panglacial Wurm attacked for 9 and won the game')
        else:
            controller.log.append(f'  Panglacial Wurm attacked for 9')
