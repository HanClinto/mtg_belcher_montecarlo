
# CardList extends the list class to add a few methods for dealing with
# a list of cards.
import pickle
#import msgpack as pickle
import random
import time
from typing import List

MAXINT = 2**31 - 1
LOGGING_ENABLED = False

def get_card_by_name(name):
    for subclass in Card.__subclasses__():
        if subclass.name == name:
            return subclass
    return None
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
        # Find subclasses of Card that have a name that matches the card name and add each one to the deck
        card_class = get_card_by_name(cardname)
        if not card_class:
            print ("Warning: Card not found: " + cardname)
        else:
            for i in range(int(quantity)):
                self.append(card_class())

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
            if card.name == name or card.cardtype == name:
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
            #print(f'Unable to find card "{card}"')
            return None
        else:
            return card


class Player:
    land_drops:int = 0
    lands:int = 0
    colorless_lands:int = 0
    mana_pool:int = 0
    colorless_mana_pool:int = 0
    persistent_mana_pool:int = 0 # This is mana that is from on-demand sources like Elvish Spirit Guide, and Lotus Petal. Don't spend it except as a last resort.
    persistent_colorless_mana_pool:int = 0 # This is non-green mana that is from on-demand sources Simian Spirit Guide. Don't spend it except as a last resort, but spend it before regular persistent mana.
    current_turn:int = 0
    creature_died_this_turn:bool = False
    life_total:int = 20
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
        self.debug_log(f" Draw {quantity} card(s)")
        for i in range(quantity):
            self.hand.append(self.deck.draw())

    def mulligan(self, mulligan_to=6):
        # Only permit a mulligan on turn 0 before any actions are taken.
        assert self.current_turn == 0, "Cannot mulligan after turn 0"

        self.debug_log(f" Mulligan to {mulligan_to} cards")
        # Return all cards in hand to the deck
        self.deck.extend(self.hand)
        # Shuffle
        self.deck.shuffle()
        # Draw new hand
        self.draw(mulligan_to)
        # TODO: Implement London Mulligan rules instead of this variety.

        # Run upkeep and everything for the new hand
        self.debug_log(f"Beginning turn {self.current_turn} after mulligan: " + self.short_str())
        # Untap all mana sources and immediately tap them all for mana
        self.mana_pool = self.lands
        self.colorless_mana_pool = self.colorless_lands

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

    def has_mana(self, total_cost, colorless_cost=0):
        colored_cost = total_cost - colorless_cost

        colored_mana_available = self.mana_pool + self.persistent_mana_pool
        colorless_mana_available = self.colorless_mana_pool + self.persistent_colorless_mana_pool

        return (colored_cost <= colored_mana_available
            and total_cost <= colored_mana_available + colorless_mana_available)

    def adjust_mana_pool(self, total_cost, colorless_cost=0):
        starting_total_mana = self.mana_pool + self.colorless_mana_pool + self.persistent_mana_pool + self.persistent_colorless_mana_pool
        remaining_colored_cost = total_cost - colorless_cost
        remaining_colorless_cost = colorless_cost

        ### Stage 1: Colorless costs
        ## 1) Spend temporary colorless mana on our colorless costs first
        ## 2) Spend spare temporary colored mana on our remaining colorless costs next
        ## 3) Spend persistent colorless mana on our remaining colorless costs last

        ### Stage 2: Colored costs
        ## 1) Spend temporary colored mana on our colored costs first
        ## 2) Spend persistent colored mana on our remaining colored costs last

        ### Stage 1: Colorless costs
        ## Step 1.1) Spend temporary colorless mana on our colorless costs first
        colorless_usage = min(self.colorless_mana_pool, colorless_cost)
        self.colorless_mana_pool -= colorless_usage
        remaining_colorless_cost -= colorless_usage

        # Calculate how much extra colored mana do we have to spend
        spare_colored_mana = self.mana_pool - remaining_colored_cost

        ## Step 2.2) Spend spare temporary colored mana on our remaining colorless costs next
        if spare_colored_mana >= 0:
            colorless_usage = min(spare_colored_mana, remaining_colorless_cost)
            self.mana_pool -= colorless_usage
            remaining_colorless_cost -= colorless_usage

        ## Step 2.3) Spend persistent colorless mana on our remaining colorless costs last
        colorless_usage = min(self.persistent_colorless_mana_pool, remaining_colorless_cost)
        self.persistent_colorless_mana_pool -= colorless_usage
        remaining_colorless_cost -= colorless_usage

        ### Stage 2: Colored costs
        ## Step 1.1) Spend temporary colored mana on our colored costs first
        colored_usage = min(self.mana_pool, remaining_colored_cost)
        self.mana_pool -= colored_usage
        remaining_colored_cost -= colored_usage

        ## Step 2.2) Spend persistent colored mana on our remaining colored costs last
        colored_usage = min(self.persistent_mana_pool, remaining_colored_cost)
        self.persistent_mana_pool -= colored_usage
        remaining_colored_cost -= colored_usage

        # Check that we haven't overspent
        assert self.mana_pool >= 0
        assert self.colorless_mana_pool >= 0
        assert self.persistent_mana_pool >= 0
        assert self.persistent_colorless_mana_pool >= 0

        # Ensure that we spent the proper amount
        ending_total_mana = self.mana_pool + self.colorless_mana_pool + self.persistent_mana_pool + self.persistent_colorless_mana_pool
        assert starting_total_mana - total_cost == ending_total_mana

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
                print(f' ERROR: Cannot play {card}. Mana cost is {card.cost} and mana pool is {self.mana_pool} ({self.colorless_mana_pool})')
                raise Exception(f' ERROR: Cannot play {card}. Mana cost is {card.cost} and mana pool is {self.mana_pool} ({self.colorless_mana_pool})')
            else:
                self.debug_log(f" Play: {card}")
                self.hand.remove(card)
                self.adjust_mana_pool(card.cost, card.colorless_cost)
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
                self.debug_log(f" Alt play: {card}")
                self.hand.remove(card)
                self.adjust_mana_pool(card.alt_cost, card.colorless_alt_cost)
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
                self.debug_log(f" Activate: {card}")
                self.adjust_mana_pool(card.activation_cost, card.colorless_activation_cost)
                card.activate(self)

    def panglacial_potential(self, additional_cost) -> bool:
        if not self.panglacial_in_deck:
            return False
        # Check if we have a Panglacial Wurm in our deck, and have enough mana to cast it.
        return (self.has_mana(PanglacialWurm.cost + additional_cost, PanglacialWurm.colorless_cost)
            and self.deck.count("Panglacial Wurm") > 0)

    def check_panglacial(self):
        if self.panglacial_potential(0):
            self.can_cast_wurm_now = True

    def has_spellmastery(self):
        # If there are two or more instant and sorcery cards in your graveyard, you have spellmastery
        return self.graveyard.count_cards('Instant') + self.graveyard.count_cards('Sorcery') >= 2
    
    def has_delirium(self):
        # If there are four or more card types among cards in your graveyard, you have delirium
        card_types = []
        for card in self.graveyard:
            if card.cardtype not in card_types:
                card_types.append(card.cardtype)
        return len(card_types) >= 4

    def trigger_landfall(self, landcount=1):
        # If there are cards on the table that trigger landfall, then trigger them.
        for card in self.table:
            # If the card has a landfall ability, then trigger it.
            if hasattr(card, 'do_landfall'):
                for i in range(landcount):
                    card.do_landfall(self)

    def start_game(self) -> 'Player':
        # If it's the first turn, shuffle up and draw 7 cards
        if self.current_turn == 0:
            self.deck.shuffle()
            self.draw(7)

    def start_turn(self) -> 'Player':
        # Increment turn count
        self.current_turn += 1
        self.debug_log(f"Beginning turn {self.current_turn}: " + self.short_str())
        # Untap all mana
        self.mana_pool = self.lands
        self.colorless_mana_pool = self.colorless_lands
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

        return self

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
                self.debug_log("!!!You are a win!!!")
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
            #  * If we have a Lotus Cobra we can play, then play it before we play any lands
            #  * If we have a land in our hand, play it
            #  * If we can cast Land Grant for free, then do so
            #  * If we can attack with a creature, then do so
            #  Otherwise, loop through all other cards in hand and activations (if any) and evaluate them.

            # Landfall triggers take priority, so we want to play things with landfall triggers (like Lotus Cobra and Spelunking) first
            # This is not a perfect system (I.E., what if we untap with 1 land and have an Elvish Spirit Guide + Forest + Lotus in hand)
            #  but it's a good enough approximation for now.
            # TODO: Fix our system of Elvish Spirit Guide mana by adding it to a persistent mana pool that is always spent LAST and carried from turn to turn.

            # Instant mana sources like Elvish Spirit Guide, Simian Spirit Guide, and Lotus Petal should be played first.
            #  This is because they can be used to pay for other cards that we play this turn.
            if self.can_alt_play('Elvish Spirit Guide'):
                copy = self.copy()
                copy.alt_play('Elvish Spirit Guide')
                next_states.append(copy)
            elif self.can_alt_play('Simian Spirit Guide'):
                copy = self.copy()
                copy.alt_play('Simian Spirit Guide')
                next_states.append(copy)
            # Next, cards with landfall triggers should be played next.
            elif self.can_play('Lotus Cobra'):
                copy = self.copy()
                copy.play('Lotus Cobra')
                next_states.append(copy)
            # Land drops take next priority -- always do those first UNLESS we have a Lotus Cobra in hand that we can cast
            # If we can drop a land, and we have 1 or more lands in hand, then play them.
            elif self.land_drops > 0 and self.hand.count_cards('Forest') > 0:
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
            # Check to see if we can attack with any creatures
             # Can we attack with Chancellor?
            elif self.can_activate('Chancellor of the Tangle'):
                # Find the first copy of Chancellor in our new table that can be activated.
                copy = self.copy()
                copy.activate('Chancellor of the Tangle')
                next_states.append(copy)
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
                    if card not in unique_hand_cards and not card.skip_playing_this_turn:
                        unique_hand_cards.append(card)

                # For every card, if it is flagged to consider not playing it, then create a branch where we don't play it.
                for card_idx, card in enumerate(self.hand):
                    # TODO: Fix this
                    if False and card.consider_not_playing and not card.skip_playing_this_turn:
                        copy = self.copy()
                        copy_card = copy.hand[card_idx]
                        copy_card.skip_playing_this_turn = True
                        next_states.append(copy)

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
                # NOTE: Examples of cards that may benefit from this are:
                #   * Simian Spirit Guide
                #   * Elvish Spirit Guide
                #   * Possibly Caravan Vigil...?
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
        s += f" Colorless: {self.colorless_mana_pool} / {self.colorless_lands}\n"
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
        return f"{self.current_turn})  LID: {self.deck.count_cards('Forest')}  H: {len(self.hand)}  Mana: {self.mana_pool}/{self.lands} ({self.colorless_mana_pool}/{self.colorless_lands}) [{self.hand.count_cards('Forest')}]  OLife: {self.opponent_lifetotal} '{self.log[-1]}'"

    # Methods to support testing
    def debug_force_get_card_in_hand(self, card_name, quant=1) -> 'Card':
        # Ensure that the player has the given card in their hand. If they don't, then retrieve on from the deck.
        while self.hand.count_cards(card_name) < quant:
            assert self.deck.count_cards(card_name) > 0, f"ERROR: Cannot find required {quant} {card_name} in deck"
            card = self.deck.find_and_remove(card_name)[0]
            self.hand.append(card)
        return self.hand.find(card_name)[0]

    def debug_log(self, msg):
        if LOGGING_ENABLED:
            self.log.append(msg)

# Define generic Card class that has a cost, name, and ability function
class Card:
    name:str = 'card'
    cost:int = 0
    colorless_cost:int = 0 # Colorless portion of the cost
    alt_cost:int = MAXINT
    colorless_alt_cost:int = 0 # Colorless portion of the alternate cost
    activation_cost:int = MAXINT # Assume all activations are colorless
    colorless_activation_cost:int = 0 # Colorless portion of the activation cost
    cardtype:str = 'None'
    prefer_alt:bool = False # If the alternate cost is available, don't evaluate the regular cost.  This is useful for cards like Caravan Vigil and Land Grant.
    deck_max_quant:int = 4 # How many of these cards can we play in our deck?
    consider_not_playing:bool = False # Set to True if this is a card that we can potentially gain advantage by saving to a future turn -- even if we can play it. Example would be cards that add mana, like Elvish Spirit Guide.
    skip_playing_this_turn:bool = False # Flag to mark when this card should be skipped and saved for a future turn
    power:int = None
    toughness:int = None

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
        return controller.has_mana(self.cost, self.colorless_cost)

    def alt_play(self, controller: Player):
        self.resolve(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return controller.has_mana(self.alt_cost, self.colorless_alt_cost)

    def activate(self, controller: Player):
        pass

    def can_activate(self, controller: Player) -> bool:
        return controller.has_mana(self.activation_cost, self.colorless_activation_cost)

    def is_permanent(self) -> bool:
        return not (self.cardtype == 'Instant' or self.cardtype == 'Sorcery')

    def do_upkeep(self, controller: Player):
        # Reset our skip-playing flag so that we always consider each card fresh on each turn
        self.skip_playing_this_turn = False
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
    deck_max_quant:int = 10 # No limit on lands to play in our deck

    def can_play(self, controller: Player) -> bool:
        return controller.land_drops > 0

    def play(self, controller: Player):
        controller.lands += 1
        controller.mana_pool += 1 # Assume that every land is immediately tapped for mana when it's played.
        controller.land_drops -= 1
        super().play(controller)
        controller.trigger_landfall()

# Lay of the Land is a card that costs 1 and has an ability that searches the deck for a land and puts it into the player's hand
class LayOfTheLand (Card):
    name = 'Lay of the Land'
    cost:int = 1
    cardtype = 'Sorcery'

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
    prefer_alt:bool = True
    consider_not_playing:bool = True # If we have Sakura-Tribe Elder, then we can get a big benefit by holding onto this card until Morbid is active.
    
    def __init__(self):
        self.mana_value = 1
        pass

    def can_play(self, controller: Player) -> bool:
        # NOTE: If there is a Sakura-Tribe Elder on the battlefield or morbid is active, then don't play this card the regular way -- wait for the better one.
        return super().can_play(controller) and (controller.table.count_cards('Sakura-Tribe Elder') == 0) and (not controller.creature_died_this_turn) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

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
        controller.trigger_landfall(len(cards))

# Traverse the Ulvenwald is a card that costs 1 and has an ability that says: Search your library for a basic land card, reveal it, put it into your hand, then shuffle your library. Delirium - If there are four or more card types among cards in your graveyard, instead search your library for a creature or land card, reveal it, put it into your hand, then shuffle your library.
#  We will implement the delirium mode as an alternate play, so that we can more easily track its effect on the game.
# NOTE: Currently I don't think there is much (any) self-mill, so probably unlikely to get Delirium. Don't bother with this right now.
"""
class TraverseTheUlvenwald (Card):
    name = 'Traverse the Ulvenwald'
    cost:int = 1
    colorless_cost:int = 0
    alt_cost:int = 1
    colorless_alt_cost:int = 0
    cardtype = 'Sorcery'
    prefer_alt:bool = True

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))
    
    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.has_delirium()
    
    def alt_play(self, controller: Player):
        card_priorities = ['Street Wraith', 
        # TODO: Which land or creature do we want to find?
        # Maybe Street Wraith so that we can turn this into a cycler...?
        # Maybe our highest CMC creature so that we can cast it eventually?
        # Maybe the creature with the highest CMC that's <= our current mana pool?
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().alt_play(controller)
"""
        
# Sakura-Tribe Elder is a creature that costs 2 and has an ability that says: Sacrifice Sakura-Tribe Elder: Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.
class SakuraTribeElder (Card):
    name = 'Sakura-Tribe Elder'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
    cardtype = 'Creature'
    activation_cost:int = 0
    power:int = 1
    toughness:int = 1

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
        # Trigger landfall
        controller.trigger_landfall(len(cards))

# Arboreal Grazer is a creature that costs 1 that says "When Arboreal Grazer enters the battlefield, you may put a land card from your hand onto the battlefield tapped."
class ArborealGrazer (Card):
    name = 'Arboreal Grazer'
    cost:int = 1
    cardtype = 'Creature'
    power:int = 0
    toughness:int = 3

    def play(self, controller: Player):
        super().play(controller)
        # Put a land into play tapped
        # NOTE: Cannot be used for MDFCs
        cards = controller.hand.find_and_remove('Forest', 1)
        controller.table.extend(cards)
        controller.lands += len(cards)
        controller.trigger_landfall(len(cards))

    # Only let us play this card if we have more forests in hand than land drops
    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.hand.count_cards('Forest') > controller.land_drops

# Krosan Wayfarer is a creature that costs 1 that says "Sacrifice Krosan Wayfarer: You may put a land card from your hand onto the battlefield."
class KrosanWayfarer (Card):
    name = 'Krosan Wayfarer'
    cost:int = 1
    cardtype = 'Creature'
    activation_cost:int = 0
    power:int = 1
    toughness:int = 1

    def play(self, controller: Player):
        super().play(controller)

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller)

    def can_activate(self, controller: Player) -> bool:
        return (super().can_activate(controller) 
            and self in controller.table 
            and controller.hand.count_cards('Forest') > controller.land_drops)

    def activate(self, controller: Player):
        super().activate(controller)
        # Put a land into play untapped
        cards = controller.hand.find_and_remove('Forest', 1)
        controller.table.extend(cards)
        controller.lands += len(cards)
        controller.mana_pool += len(cards)
        # Immediately sacrifice this
        controller.table.remove(self)
        controller.graveyard.append(self)
        controller.trigger_landfall(len(cards))

# Skyshroud Ranger is a creature that costs 1 that says "T: You may put a land card from your hand onto the battlefield. Activate only as a sorcery."
# Sakura-Tribe Scout is a near-identical card.
# NOTE: If this card sees play, then can also add the 2-mana big brothers, Scaled Herbalist, Llanowar Scout, and .
class SkyshroudRanger (Card):
    name = 'Skyshroud Ranger'
    cost:int = 1
    cardtype = 'Creature'
    activation_cost:int = 0
    power:int = 1
    toughness:int = 1
    deck_max_quant:int = 8 # Because Sakura-Tribe Scout is a functional duplicate, we can play 8 of these in our deck.

    def __init__(self):
        self.is_tapped = False

    def play(self, controller: Player):
        # Represent summoning sickness by coming into play tapped.
        self.is_tapped = True
        super().play(controller)

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped 
            and controller.hand.count_cards('Forest') > 0
            and self in controller.table)

    def activate(self, controller: Player):
        # Put a land into play untapped
        # NOTE: Cannot be used for MDFCs
        cards = controller.hand.find_and_remove('Forest', 1)
        controller.table.extend(cards)
        controller.lands += len(cards)
        controller.trigger_landfall(len(cards))
        controller.mana_pool += len(cards)

        self.is_tapped = True

# Reclaim the Wastes is a card that costs 1 and when played, searches the deck for a land and puts it into the player's hand.
#  It has an alternate cost of 4 that searches for 2 lands instead.
class ReclaimTheWastes (Card):
    name = 'Reclaim the Wastes'
    cost:int = 1
    alt_cost:int = 4
    colorless_alt_cost:int = 3 # Colorless portion of the alternate cost
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
    colorless_cost:int = 1 # Colorless portion of the cost
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
    colorless_cost:int = 4 # Colorless portion of the cost
    activation_cost:int = 3
    colorless_activation_cost:int = 3 # Colorless portion of the activation cost
    cardtype = 'Artifact'

    def __init__(self):
        self.is_tapped = False

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    # NOTE: Should we allow the user to activate with forests still remaining in the deck?  It feels very shuffle-dependent, and I would like to optimize for the case where we can belcher the opponent out of the game guaranteed.
    def can_activate(self, controller: Player) -> bool:
        return (super().can_activate(controller)
            and not self.is_tapped)
            # NOTE: Experimentally, we can try to ONLY allow activation if there are no lands in the deck.  This will make the game more difficult, but it will also make it more fair because the AI won't be able to know "secret knowledge" of how the deck is stacked.
            # and controller.deck.count_cards('Forest') == 0)

    def activate(self, controller: Player):
        self.is_tapped = True
        cards, revealed_card = controller.deck.reveal_cards_until('Forest')
        # HACK: To make it less appealing to belcher early, let's make it so that belcher only does half damage.
        damage = int(len(cards) * 2.0 / 3.0)
        controller.opponent_lifetotal -= damage
        controller.deck.put_on_bottom(cards)
        lands_in_deck = controller.deck.count_cards('Forest')
        controller.debug_log(f'  Belcher with {lands_in_deck} lands in deck')

# Elvish Mystic is a card that costs 1 and has an ability that increases a player's mana pool by 1
#  NOTE: This is a bit of a hack, but when we play it we simply increase the player's land count by 1,
#   which means that the player will have extra mana in their mana pool starting *next* turn.
class ElvishMystic (Card):
    name = 'Elvish Mystic'
    cost:int = 1
    cardtype = 'Creature'
    deck_max_quant:int = 8 # Because Llanowar Elves is functionally a copy of Elvish Mystic, we can set this playable number to 8 and not include Llanowar Elves in the permutation set.
    power:int = 1
    toughness:int = 1

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
    deck_max_quant:int = 0 # Turn off this card for now
    power:int = 1
    toughness:int = 1

    def __init__(self):
        self.is_tapped = True
        pass

    def play(self, controller: Player):
        # Instead of activating to add mana to our mana pool, just treat it as a new land so we don't have as many branching permutations.
        controller.lands += 1
        super().play(controller)

# Arbor Elf is a creature of cost 1 that has an ability that adds 1 to the mana pool, unless there is a Wild Growth in play, in which case it adds 2.
class ArborElf (Card):
    name = 'Arbor Elf'
    cost:int = 1
    cardtype = 'Creature'
    power:int = 1
    toughness:int = 1

    def play(self, controller: Player):
        # Represent summoning sickness by coming into play tapped.
        self.is_tapped = True
        super().play(controller)

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped 
            and self in controller.table 
            and controller.table.count_cards('Forest') > 0)

    def activate(self, controller: Player):
        # If we have Wild Growth in play, assume they're all on the same land, so untap them all at the same time. H.T. bakeraj4 for the change!
        numWildGrowth = controller.table.count_cards('Wild Growth')

        # Can only add mana if there is at least one land in play
        if controller.table.count_cards('Forest') > 0:
            controller.mana_pool += 1 + numWildGrowth

        self.is_tapped = True

# Rampant Growth is a card with an ability: Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.
class RampantGrowth(Card):
    name = 'Rampant Growth'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
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
        controller.table.extend(cards)
        controller.lands += len(cards)
        super().play(controller)
        controller.trigger_landfall(len(cards))

# Nissa's Pilgrimage is a card with the ability: Search your library for up to two basic Forest cards, reveal those cards, and put one onto the battlefield tapped and the rest into your hand. Then shuffle your library.  If there are two or more instant and/or sorcery cards in your graveyard, search your library for up to three basic Forest cards instead of two.
class NissasPilgrimage(Card):
    name = 'Nissa\'s Pilgrimage'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    alt_cost:int = 3
    colorless_alt_cost:int = 2 # Colorless portion of the alternate cost
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
            controller.trigger_landfall()
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
            controller.trigger_landfall()
            controller.lands += 1

        # Add the rest to the hand
        controller.hand.extend(cards)
        super().alt_play(controller)

# Wall of Roots is a card that costs 2 and has an ability that increases a player's mana pool by 1
# NOTE: This is a bit of a hack.  For now we're going to treat this as a land that enters untapped, but doesn't remove a Forest from the deck.
#  This lets us not have to deal with the branching permutations of activating it, and very rarely would a game go long enough that we could ever kill it off from 5 activations.
# If the AI starts to over-value Wall of Roots, consider restoring the prior implementation (saved for reference)
class WallOfRoots (Card):
    name = 'Wall of Roots'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
    cardtype = 'Creature'
    power:int = 0
    toughness:int = 5

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
    colorless_cost:int = 1 # Colorless portion of the cost
    cardtype = 'Sorcery'

    def play(self, controller: Player):
        controller.land_drops += 1
        controller.draw()
        super().play(controller)

# Chancellor of the Tangle costs 7 and has an ability that says: You may reveal this card from your opening hand. If you do, at the beginning of your first main phase, add 1 to your mana pool
class ChancellorOfTheTangle(Card):
    name = 'Chancellor of the Tangle'
    cost:int = 7
    colorless_cost:int = 4 # Colorless portion of the cost
    cardtype = 'Creature'
    activation_cost:int = 0 # Costs nothing to attack
    power:int = 6
    toughness:int = 7

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
                controller.debug_log(f'  Chancellor of the Tangle adding 1 to mana pool')
                controller.mana_pool += 1

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped) and (self in controller.table)

    def activate(self, controller: Player):
        self.is_tapped = True
        controller.opponent_lifetotal -= 6
        if controller.opponent_lifetotal <= 0:
            controller.debug_log(f'  Chancellor of the Tangle attacked for 6 and won the game')
        else:
            controller.debug_log(f'  Chancellor of the Tangle attacked for 6')

# Wild Growth is an enchantment that costs 1 and has an ability that says: Whenever enchanted land is tapped for mana, its controller adds an additional mana
class WildGrowth(Card):
    name = 'Wild Growth'
    cost:int = 1
    cardtype = 'Enchantment'

    # Only allow this card to be played if the table contains a Forest
    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.table.count_cards('Land') > 0

    def play(self, controller: Player):
        controller.lands += 1 # Simulate effect by just adding an additional land
        # If there is at least one unused green mana when this is played, then add 1 to the mana pool, implying that we played this against an untapped land.
        #  Note: This isn't perfect, but it's probably good 'nuff.
        if controller.mana_pool > 0:
            controller.mana_pool += 1
        super().play(controller)

# Search for Tomorrow is a sorcery that costs 3 and says: Search your library for a basic land card, put it onto the battlefield, then shuffle. Suspend 2— (Rather than cast this card from your hand, you may pay  and exile it with two time counters on it. At the beginning of your upkeep, remove a time counter. When the last is removed, cast it without paying its mana cost.)
class SearchForTomorrow(Card):
    name = 'Search for Tomorrow'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    alt_cost:int = 1
    cardtype = 'Sorcery'

    def __init__(self):
        self.time_counters = 0

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.table.extend(cards)
        controller.lands += len(cards)
        controller.mana_pool += 1 # The land comes into play untapped, so immediately add it to the mana pool.
        super().play(controller)
        controller.trigger_landfall(len(cards))

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
            controller.debug_log(f'  Suspend: Search for Tomorrow has {self.time_counters} time counters')
            # If the last time counter is removed, then cast the card
            if self.time_counters == 0:
                self.play(controller)

# Recross the Paths is a sorcery that costs 3 and says: Reveal cards from the top of your library until you reveal a land card. Put that card onto the battlefield and the rest on the bottom of your library in any order. Clash with an opponent. If you win, return Recross the Paths to its owner's hand.
class RecrossThePaths(Card):
    name = 'Recross the Paths'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    cardtype = 'Sorcery'
    alt_cost:int = 3
    colorless_alt_cost:int = 2 # Colorless portion of the alternate cost

    def __init__(self):
        pass

    # Only play if there ARE lands in the deck
    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and controller.deck.count_cards('Forest') > 0

    def play(self, controller: Player):
        # Reveal cards from the top of the library until a land is found
        cards, land = controller.deck.reveal_cards_until('Forest')
        # If a land was found this way, then put it onto the battlefield untapped
        assert land is not None, f"Recross the Paths should always find a land. Revealed {cards} and found {land} instead."
        controller.table.append(land)
        controller.lands += 1
        controller.mana_pool += 1
        controller.debug_log(f'  Recross the Paths: Found a land')
        cards.remove(land)
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
        # NOTE Don't need to re-append this to our hand, since it's already in here, and we haven't called super.play() to auto-add it to the graveyard
        # controller.hand.append(self)
        # TODO: Make this a random chance?

    # Only alt_play if there are NO lands in the deck
    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.deck.count_cards('Forest') == 0

    def alt_play(self, controller: Player):
        # Reveal cards from the top of the library until a land is found
        cards, land = controller.deck.reveal_cards_until('Forest')
        # If a land was found this way, then put it onto the battlefield untapped
        assert land is None, f"Recross the Paths alternate play should NEVER find a land, and only stack the deck, found {land} after {cards} instead."
        controller.debug_log(f'  Recross the Paths: No land found. Deck stacked')
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
        # NOTE Don't need to re-append this to our hand, since it's already in here, and we haven't called super.play() to auto-add it to the graveyard
        # controller.hand.append(self)
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

# Panglacial Wurm is a 9/5 creature that costs 7 and says: Trample. While you're searching your library, you may cast Panglacial Wurm from your library.
class PanglacialWurm(Card):
    name = 'Panglacial Wurm'
    cost:int = 7
    colorless_cost:int = 5 # Colorless portion of the cost is 5
    activation_cost:int = 0 # Costs nothing to attack
    cardtype = 'Creature'
    deck_max_quant:int = 1 # Never play more than one of these cards
    power:int = 9
    toughness:int = 5

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
            controller.debug_log(f'  Panglacial Wurm attacked for 9 and won the game')
        else:
            controller.debug_log(f'  Panglacial Wurm attacked for 9')

# Sol Ring is an artifact that costs 1 and taps for 2 colorless mana.
class SolRing(Card):
    name = 'Sol Ring'
    cost:int = 1
    colorless_cost:int = 1 # Colorless portion of the cost
    # activation_cost:int = 0 # Costs nothing to activate
    cardtype = 'Artifact'
    deck_max_quant:int = 1 # Restricted in Vintage, so can only play 1

    # Don't permit special activation -- just add 2 to our colorless land count when activated
    def can_activate(self, controller: Player) -> bool:
        #print(f' Checking if we can activate Sol Ring...')
        return False

    def play(self, controller: Player):
        # Instead of activating this, just add to our mana pool directly.
        controller.colorless_lands += 2
        controller.colorless_mana_pool += 2
        super().play(controller)

# Simian Spirit Guide is a creature that you may exile from your hand to add 1 red (colorless) mana to your mana pool.
class SimianSpiritGuide(Card):
    name = 'Simian Spirit Guide'
    alt_cost:int = 0
    cost:int = 3 # Note that this is not castable with green, but doing it this way so that it shows up correctly in CMC lists
    colorless_cost:int = 2 # Colorless portion of the cost
    cardtype = 'Creature'
    consider_not_playing:bool = True # This is a card that we should consider not playing immediately in case we want to save the mana for later.

    # TODO: Maybe implement this as a playable creature later, but for now, just have this as a mana source.
    def can_play(self, controller: Player) -> bool:
        return False

    def alt_play(self, controller: Player):
        # Instead of activating this, just add to our mana pool directly.
        # Note that this technically should be red mana, but count it as colorless for now.
        # Only messes us up on spells like Manamorphose that would potentially care about red mana, but that's such an edge case we won't worry about it here.
        controller.colorless_mana_pool += 1
        # Exile it instead of adding it to the table
        #super().alt_play(controller)
        controller.exile.append(self)

# Elvish Spirit Guide is a creature that you may exile from your hand to add 1 green mana to your mana pool.
class ElvishSpiritGuide(Card):
    name = 'Elvish Spirit Guide'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    alt_cost:int = 0
    cardtype = 'Creature'
    consider_not_playing:bool = True # This is a card that we should consider not playing immediately in case we want to save the mana for later.

    # TODO: Maybe implement this as a playable creature later, but for now, just have this as a mana source.
    def can_play(self, controller: Player) -> bool:
        return False
    
    def can_alt_play(self, controller: Player) -> bool:
        return True

    def alt_play(self, controller: Player):
        # Instead of activating this, add it to our persistent mana pool
        controller.persistent_mana_pool += 1
        # Exile it instead of adding it to the table
        # super().alt_play(controller)
        controller.exile.append(self)

# Beneath the Sands is a sorcery that costs 3 and says: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.  Cycling 2 (2, Discard this card: Draw a card)
class BeneathTheSands(Card):
    name = 'Beneath the Sands'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    alt_cost:int = 2 # (Cycling)
    colorless_alt_cost:int = 2 # Colorless portion of the alternate cost
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        # Add a tapped forest
        controller.lands += len(cards)
        controller.table.extend(cards)
        super().play(controller)

    # Alt play is cycling
    def alt_play(self, controller: Player):
        controller.draw()
        super().alt_play(controller)

# Migration Path is a sorcery that costs 4 and says: Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle. Cycling 2 (2, Discard this card: Draw a card)
# NOTE: Explosive Vegetation and Circuitous Route are functionally identical to Migration Path (except without the cycling ability), so we will not implement them unless Migration Path sees play.
class MigrationPath(Card):
    name = 'Migration Path'
    cost:int = 4
    colorless_cost:int = 3 # Colorless portion of the cost
    alt_cost:int = 2 # (Cycling)
    colorless_alt_cost:int = 2 # Colorless portion of the alternate cost
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        search_count = 2

        cards = controller.deck.find_and_remove('Forest', search_count)
        # Put as many cards as we found onto the battlefield tapped.
        controller.lands += len(cards)
        controller.table.extend(cards)

        super().play(controller)

    # Alt play is cycling
    def alt_play(self, controller: Player):
        controller.draw()
        super().alt_play(controller)
        
# Edge of Autumn is a sorcery that costs 2 and says: If you control four or fewer lands, search your library for a basic land card, put it onto the battlefield tapped, then shuffle. Cycling - Sacrifice a Land (Sacrifice a Land, Discard this card: Draw a card)
class EdgeOfAutumn(Card):
    name = 'Edge of Autumn'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
    alt_cost:int = 0 # (Cycling)
    colorless_alt_cost:int = 0 # Colorless portion of the alternate cost
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.table.count_cards('Forest') <= 4) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))
    
    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.table.count_cards('Forest') > 0

    def play(self, controller: Player):
        # If we have 4 or fewer lands, then search for a basic land card and put it onto the battlefield tapped
        if controller.table.count_cards('Forest') <= 4:
            cards = controller.deck.find_and_remove('Forest', 1)
            controller.check_panglacial()
            # Add a tapped forest
            controller.lands += len(cards)
            controller.table.extend(cards)
        super().play(controller)

    # Alt play is cycling
    def alt_play(self, controller: Player):
        # Sacrifice a land
        # Grab a forest from the table
        cards = controller.table.find_and_remove('Forest', 1)
        # Put it into the graveyard
        controller.graveyard.extend(cards)
        # Remove the land from our mana pool for next turn
        if controller.lands > 0:
            controller.lands -= 1
        # Draw a card
        controller.draw()
        super().alt_play(controller)

# Generous Ent is a 5/7 creature that costs 6 and says: When Generous Ent enters the battlefield, create a Food token. (It's an artifact with "2, T, Sacrifice this artifact: You gain 3 life.")  Forestcycling 1 (1, Discard this card: Search your library for a Forest card, reveal it, put it into your hand, then shuffle.)
class GenerousEnt(Card):
    name = 'Generous Ent'
    cost:int = 6
    colorless_cost:int = 5 # Colorless portion of the cost
    alt_cost:int = 1 # (Forestcycling)
    colorless_alt_cost:int = 1 # Colorless portion of the alternate cost
    activation_cost:int = 0 # Costs nothing to attack
    cardtype = 'Creature'
    power:int = 5
    toughness:int = 7

    def __init__(self):
        self.is_tapped:bool = False
        pass

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    def play(self, controller: Player):
        self.is_tapped = True # Start off tapped to simulate summoning sickness
        # TODO: Create a food token
        # controller.food_tokens += 1
        super().play(controller)

    # Alt play is forestcycling
    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def alt_play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.hand.extend(cards)
        # Add this card to the graveyard
        controller.graveyard.append(self)

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped) and (self in controller.table)

    def activate(self, controller: Player):
        self.is_tapped = True
        controller.opponent_lifetotal -= self.power
        if controller.opponent_lifetotal <= 0:
            controller.debug_log(f'  Generous Ent attacked for 5 and won the game')
        else:
            controller.debug_log(f'  Generous Ent attacked for 5')
    
# Cultivate is a sorcery that costs 3 and says: Search your library for up to two basic land cards, reveal those cards, and put one onto the battlefield tapped and the other into your hand. Then shuffle your library.
class Cultivate(Card):
    name = 'Cultivate'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        search_count = 2

        cards = controller.deck.find_and_remove('Forest', search_count)
        controller.check_panglacial()

        # If we only found one card and we have a land drop available and no other forests in hand, then put it into our hand instead of onto the battlefield.
        # TODO: Perhaps only make this optimization as a line that's available under "alt play" so that we can determine if it's worth our time to consider this line of play or not.
        if len(cards) == 1 and controller.land_drops > 0 and controller.hand.count_cards('Forest') == 0:
            pass
        # Otherwise, just put the one card into play like normal.
        elif len(cards) > 0:
            card = cards.pop()
            controller.table.append(card)
            controller.lands += 1

        # Then add the rest to the hand
        controller.hand.extend(cards)
        super().play(controller)


# Beanstalk Giant is a */* creature that costs 7 and says: Beanstalk Giant's power and toughness are each equal to the number of lands you control.  Adventure - Fertile Footsteps (2G) Search your library for a basic land card, put it onto the battlefield, then shuffle.
class BeanstalkGiant(Card):
    name = 'Beanstalk Giant'
    cost:int = 7
    colorless_cost:int = 6 # Colorless portion of the cost
    alt_cost:int = 3 # (Adventure)
    colorless_alt_cost:int = 2 # Colorless portion of the alternate cost
    activation_cost:int = 0 # Costs nothing to attack
    cardtype = 'Creature'
    power:int = 6 # HACK: Instead of actually calculating our power and updating this variable, just set it to 6 for now.
    toughness:int = 6 # HACK: Instead of actually calculating our toughness and updating this variable, just set it to 6 for now.

    def __init__(self):
        self.is_tapped:bool = False
        self.has_gone_on_an_adventure:bool = False
        pass

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    def play(self, controller: Player):
        self.is_tapped = True # Start off tapped to simulate summoning sickness
        super().play(controller)

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped) and (self in controller.table)

    def activate(self, controller: Player):
        self.is_tapped = True
        num_lands = controller.table.count_cards('Forest')
        controller.opponent_lifetotal -= num_lands
        if controller.opponent_lifetotal <= 0:
            controller.debug_log(f'  Beanstalk Giant attacked for {num_lands} and won the game')
        else:
            controller.debug_log(f'  Beanstalk Giant attacked for {num_lands}')

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and not self.has_gone_on_an_adventure and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.alt_cost))
    
    # Go on an adventure -- search for a basic land card and put it onto the battlefield (untapped)
    def alt_play(self, controller: Player):
        # Add an untapped forest
        cards = controller.deck.find_and_remove('Forest', 1)
        controller.check_panglacial()
        controller.table.extend(cards)
        controller.lands += 1
        controller.mana_pool += 1 # The land comes into play untapped, so immediately add it to the mana pool.
        # Don't add ourselves to the table, but keep this card in the hand -- though mark us as having gone on an adventure, so cannot be alt-played again.
        #super().alt_play(controller)
        self.has_gone_on_an_adventure = True

# Grow from the Ashes is a sorcery that costs 3 and says: Kicker 2 (You may pay an additional 2 as you cast this spell.) Search your library for a basic land card, put it onto the battlefield, then shuffle. If this spell was kicked, instead search your library for two basic land cards, put them onto the battlefield, then shuffle.
class GrowFromTheAshes(Card):
    name = 'Grow from the Ashes'
    cost:int = 3
    colorless_cost:int = 2 # Colorless portion of the cost
    alt_cost:int = 5 # (Cast w/ kicker)
    colorless_alt_cost:int = 4 # Colorless portion of the alternate cost
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and (controller.deck.count_cards('Forest') > 1)
    
    def play(self, controller: Player):
        self.do_effect(controller, 1)

    def alt_play(self, controller: Player):
        self.do_effect(controller, 2)

    def do_effect(self, controller: Player, search_count:int):
        cards = controller.deck.find_and_remove('Forest', search_count)
        controller.check_panglacial()

        # Put as many cards as we found onto the battlefield untapped.
        controller.lands += len(cards)
        controller.table.extend(cards)
        # The lands come into play untapped, so immediately add them to our mana pool
        controller.mana_pool += len(cards)

        super().play(controller)

# Nissa's Triumph is a sorcery that costs 2 and says: Search your library for up to two basic Forest cards. If you control a Nissa planeswalker, instead search your library for up to three land cards. Reveal those cards, put them into your hand, then shuffle.
# NOTE: We will not implement the Nissa planeswalker check, as we are not currently implementing planeswalkers.
# NOTE: Seek the Horizon is functionally similar to Nissa's Triump, except for a cost of 4 instead of 2, but lets the player search for an additional land. We will not be implementing this one unless Nissa's Triumph sees play.
class NissasTriumph(Card):
    name = 'Nissa\'s Triumph'
    cost:int = 2
    colorless_cost:int = 0 # Colorless portion of the cost
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 2)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

# Manamorphose is an instant that costs 2 and says: Add two mana in any combination of colors. Draw a card.
class Manamorphose(Card):
    name = 'Manamorphose'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
    cardtype = 'Instant'

    def play(self, controller: Player):
        # Add two mana in any combination of colors
        controller.mana_pool += 2
        # Draw a card
        controller.draw()
        super().play(controller)

# Tangled Florahedron/Tangled Vale is a DFC that, on the front face, is a creature that costs 2 and says: T: Add G.  On the back face, it is a land that enters the battlefield tapped.
class TangledFlorahedron(Card):
    name = 'Tangled Florahedron'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
    cardtype = 'Creature'
    alt_cost:int = 0
    power:int = 1
    toughness:int = 1

    def play(self, controller: Player):
        # Instead of activating to add mana to our mana pool, just treat it as a new land so we don't have as many branching permutations.
        controller.lands += 1
        super().play(controller)

    # Alt play is playing it as a tapped land on its backside
    def can_alt_play(self, controller: Player) -> bool:
        return controller.land_drops > 0

    def alt_play(self, controller: Player):
        controller.lands += 1
        # This comes in tapped, so we can't immediately add it to our mana_pool
        controller.land_drops -= 1
        # Change the name and cardtype to the backside
        self.cardtype = 'Land'
        super().alt_play(controller)
        # Adjust the name after play so that it shows up in the log correctly
        self.name = 'Tangled Vale'

# Disciple of Freyalise is a DFC Creature // Land that is 3/3, costs 3GGG and says: When Disciple of Freyalise enters the battlefield, you may sacrifice another creature. If you do, you gain X life and draw X cards, where X is that creature’s power.
# On the back face, it is a Land that says: As Garden of Freyalise enters the battlefield, you may pay 3 life. If you don’t, it enters the battlefield tapped.
class DiscipleOfFreyalise(Card):
    name = 'Disciple of Freyalise'
    cost:int = 6
    colorless_cost:int = 3 # Colorless portion of the cost
    cardtype = 'Creature'
    alt_cost:int = 0
    power:int = 3
    toughness:int = 3
    deck_max_quant:int = 0 # Turn off this card for now because it doesn't release until Modern Masters 3

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    def play(self, controller: Player):
        # Find the creature with the highest power and sacrifice it
        highest_power = 0
        highest_power_creature = None
        for card in controller.table:
            if card.cardtype == 'Creature' and card.power > highest_power:
                highest_power = card.power
                highest_power_creature = card

        if highest_power_creature is not None:
            controller.table.remove(highest_power_creature)
            controller.graveyard.append(highest_power_creature)
            controller.life_total += highest_power
            controller.draw(highest_power)
        
        super().play(controller)

    def can_activate(self, controller: Player) -> bool:
        return super().can_activate(controller) and not self.is_tapped
    
    def activate(self, controller: Player):
        self.is_tapped = True
        controller.opponent_lifetotal -= 3
        if controller.opponent_lifetotal <= 0:
            controller.debug_log(f'  Disciple of Freyalise attacked for 3 and won the game')
        else:
            controller.debug_log(f'  Disciple of Freyalise attacked for 3')

    # Alt play is playing it as a land on its backside
    def can_alt_play(self, controller: Player) -> bool:
        return controller.land_drops > 0

    def alt_play(self, controller: Player):
        controller.lands += 1
        controller.land_drops -= 1
        
        # If we have the life available, then we can play this untapped. Otherwise, it comes in tapped.
        if controller.life_total > 3:
            controller.life_total -= 3
            controller.mana_pool += 1

        # Change the name and cardtype to the backside
        self.cardtype = 'Land'
        super().alt_play(controller)
        # Adjust the name after play so that it shows up in the log correctly
        self.name = 'Garden of Freyalise'

# Journey of Discovery is a sorcery that costs 3 and says: Choose one — Search your library for up to two basic land cards, reveal them, put them into your hand, then shuffle; or you may play up to two additional lands this turn. Entwine 2G (Choose both if you pay the entwine cost.)
class JourneyOfDiscovery(Card):
    name = 'Journey of Discovery'
    cost:int = 3 # Search for lands
    colorless_cost:int = 2 # Colorless portion of the cost
    alt_cost:int = 3 # Additional land drops
    colorless_alt_cost:int = 2 # Colorless portion of the alternate cost
    #activation_cost:int = 6 # We're going to count Entwine as the activation
    #colorless_activation_cost:int = 4 # Colorless portion of the activation
    cardtype = 'Sorcery'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return super().can_play(controller) and (controller.deck.count_cards('Forest') > 0 or controller.panglacial_potential(self.cost))

    # Check to see if the number of lands we have in our hand is greater than the number of land drops we have remaining
    # TODO: Also check to see if we have MDFC lands in hand that we can play instead...?
    def can_alt_play(self, controller: Player) -> bool:
        return super().can_alt_play(controller) and controller.hand.count_cards('Forest') > controller.land_drops

    def play(self, controller: Player):
        cards = controller.deck.find_and_remove('Forest', 2)
        controller.check_panglacial()
        controller.hand.extend(cards)
        super().play(controller)

    def alt_play(self, controller: Player):
        controller.land_drops += 2
        super().alt_play(controller)

    # TODO: See if we can implement the entwine cost as an activation cost -- need to modify things so that we can activate this card from the hand?
    #def can_activate(self, controller: Player) -> bool:
    #    return super().can_activate(controller) and controller.mana_pool >= self.activation_cost

# Street Wraith is a 3/4 creature that costs 3BB, but the interesting bit is that it says: Cycling - Pay 2 life. (Pay 2 life, Discard this card: Draw a card.)
#  We will never cast it, but will always cycle it for 2 life.
class StreetWraith(Card):
    name = 'Street Wraith'
    cost:int = MAXINT # Assume we can never cast this card. Manamorphose would technically let us cast it, but let's not worry about that right now.
    colorless_cost:int = 3 # Colorless portion of the cost
    alt_cost:int = 0
    power:int = 3
    toughness:int = 4
    cardtype = 'Creature'

    def __init__(self):
        pass

    def can_play(self, controller: Player) -> bool:
        return False

    def can_alt_play(self, controller: Player) -> bool:
        return controller.life_total > 2

    def alt_play(self, controller: Player):
        controller.life_total -= 2
        controller.draw()
        controller.graveyard.append(self)

# TODO: Consider Lotus Cobra as a way to ramp mana when we're adding lots of lands to the battlefield
# Lotus Cobra is a 2/1 creature that costs 1G and says: Landfall — Whenever a land enters the battlefield under your control, add one mana of any color.
class LotusCobra(Card):
    name = 'Lotus Cobra'
    cost:int = 2
    colorless_cost:int = 1 # Colorless portion of the cost
    cardtype = 'Creature'
    power:int = 2
    toughness:int = 1

    def __init__(self) -> None:
        self.is_tapped = True
        super().__init__()

    def do_upkeep(self, controller: Player):
        self.is_tapped = False

    def play(self, controller: Player):
        self.is_tapped = True
        super().play(controller)

    def can_activate(self, controller: Player) -> bool:
        return (not self.is_tapped) and (self in controller.table)
    
    def activate(self, controller: Player):
        self.is_tapped = True
        controller.opponent_lifetotal -= self.power
        if controller.opponent_lifetotal <= 0:
            controller.debug_log(f'  Lotus Cobra attacked for 2 and won the game')
        else:
            controller.debug_log(f'  Lotus Cobra attacked for 2')

    def do_landfall(self, controller: Player):
        # Add a green on every landfall
        controller.mana_pool += 1
        controller.debug_log(f'  Lotus Cobra: Landfall triggered, adding 1 green mana')

