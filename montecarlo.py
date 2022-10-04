import cards
import sys
import random
import time

deckrange = [
{'quant':1, 'min_quant':0, 'max_quant':4, 'name':"Arboreal Grazer"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Caravan Vigil"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Sakura-Tribe Elder"},
{'quant':2, 'min_quant':0, 'max_quant':4, 'name':"Lay of the Land"},
{'quant':2, 'min_quant':0, 'max_quant':8, 'name':"Elvish Mystic"},
{'quant':2, 'min_quant':0, 'max_quant':4, 'name':"Ancient Stirrings"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Reclaim the Wastes"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Wild Growth"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Land Grant"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Rampant Growth"},
{'quant':2, 'min_quant':0, 'max_quant':4, 'name':"Explore"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Wall of Roots"},
{'quant':3, 'min_quant':0, 'max_quant':4, 'name':"Search for Tomorrow"},
{'quant':3, 'min_quant':0, 'max_quant':4, 'name':"Nissa's Pilgrimage"},
{'quant':3, 'min_quant':0, 'max_quant':4, 'name':"Recross the Paths"},
{'quant':3, 'min_quant':0, 'max_quant':4, 'name':"Goblin Charbelcher"},
{'quant':4, 'min_quant':0, 'max_quant':4, 'name':"Chancellor of the Tangle"},
{'quant':7, 'min_quant':7, 'max_quant':7, 'name':"Forest"}
]


def get_deck_variants(deckrange):
    """Get all possible deck variants"""
    decks_61 = []
    cards_61 = []
    decks_59 = []
    cards_59 = []

    deck_baseline = ""
    for card in deckrange:
        deck_baseline += str(card['quant']) + " " + card['name'] + "\n"
    
    # 61-card decks
    for chosen_card in deckrange:
        deck = ""
        if chosen_card['quant'] < chosen_card['max_quant']:
            for card in deckrange:
                quant = card['quant']
                if card['name'] == chosen_card['name']:
                    quant += 1
                deck += str(quant) + " " + card['name'] + "\n"
            decks_61.append(deck)
            cards_61.append(chosen_card['name'])

    # 59-card decks
    for chosen_card in deckrange:
        deck = ""
        if chosen_card['quant'] > chosen_card['min_quant']:
            for card in deckrange:
                quant = card['quant']
                if card['name'] == chosen_card['name']:
                    quant -= 1
                deck += str(quant) + " " + card['name'] + "\n"
            decks_59.append(deck)
            cards_59.append(chosen_card['name'])

    return deck_baseline, decks_61, cards_61, decks_59, cards_59



deep_leaf = None

def print_tree(state, depth = 0):
    print ("  "*depth, state.short_str())
    for child in state.childstates:
        print_tree(child, depth+1)

def get_all_leaf_nodes(state, depth=0):
    global deep_leaf
    if depth > 1000:
        deep_leaf = state
        print(f'Recursion limit reached at depth {depth}')
        print_tree(deep_leaf)
        deep_leaf.dumplog()
        raise RecursionError("Recursion limit exceeded")

    if len(state.childstates) == 0:
        return [state]
    else:
        leaf_nodes = []
        for child in state.childstates:
            leaf_nodes.extend(get_all_leaf_nodes(child, depth+1))
        return leaf_nodes

def find_fastest_win(state, maxturn = 10):
    did_win = False
    win_state = None
    max_leaf_nodes = 0

    action_count = 0
    while not did_win:
        action_count += 1
        leaf_nodes = get_all_leaf_nodes(state)
        
        if len(leaf_nodes) > max_leaf_nodes:
            max_leaf_nodes = len(leaf_nodes)

        # Find the minimum turn in the leaf nodes
        min_turn = min([leaf.current_turn for leaf in leaf_nodes])

        # Find any leaf nodes that are at the minimum turn
        min_turn_leaf_nodes = [leaf for leaf in leaf_nodes if leaf.current_turn == min_turn]

        # Find any leaf nodes where check_win() is True
        win_leaf_nodes = [leaf for leaf in min_turn_leaf_nodes if leaf.check_win()]

        if len(win_leaf_nodes) > 0:
            did_win = True
            win_state = win_leaf_nodes[0]
            break
        elif min_turn > maxturn:
            break
        
        # If we have more than leaf_node_limit leaf nodes, randomly select leaf_node_limit of them
        leaf_node_limit = 200000
        if len(min_turn_leaf_nodes) > leaf_node_limit:
            print(f'Warning: Exceeding leaf node limit of {leaf_node_limit} at turn {min_turn} with {len(min_turn_leaf_nodes)} leaf nodes')
            # Print off five random leaf nodes
            for i in range(5):
                print(f'*** Random leaf node {i}:')
                random_leaf = random.choice(min_turn_leaf_nodes)
                print_tree(random_leaf)
                print(random_leaf)
                random_leaf.dumplog()

            #random.seed(state.randseed)
            #min_turn_leaf_nodes = random.sample(min_turn_leaf_nodes, leaf_node_limit)

        # Step through all min_turn_leaf_nodes
        for leaf in min_turn_leaf_nodes:
            if not did_win:
                next_states = leaf.step_next_actions()
            for next_state in next_states:
                if not did_win and next_state.check_win():
                    did_win = True
                    win_state = next_state
                    break

    return win_state, action_count, max_leaf_nodes


def test_decklist(decklist, num_trials, max_turns):
    #end_reasons = {}
    durations = []
    total_turns = 0

    winning_log_messages = {}

    print (f'Testing decklist: {decklist}')

    for i in range(num_trials):
        then = time.time()
        randseed = random.randint(0, 2**32-1)
        player = cards.Player(decklist, randseed)
        player.start_turn()
        win_state, action_count, max_leaf_nodes = find_fastest_win(player, max_turns)

        duration = time.time() - then
        durations.append(duration)
            
        won_turn = max_turns + 1
        end_reason = "Did not win in time"

        if win_state is not None:
            print (f'  Found win in {action_count} actions and {win_state.current_turn} turns: {win_state.short_str()}')
            won_turn = win_state.current_turn
            end_reason = win_state.log[-1].strip()

            for log_message in win_state.log:
                log_message = log_message.strip()
                if log_message not in winning_log_messages:
                    winning_log_messages[log_message] = 0
                winning_log_messages[log_message] += 1
        else:
            print (f'  Did not find win.  Max leaf nodes: {max_leaf_nodes}')

        # Remove the player object so that we don't have to wait for the garbage collector
        del player

        total_turns += won_turn

        #if end_reason not in end_reasons:
        #    end_reasons[end_reason] = 1
        #else:
        #    end_reasons[end_reason] += 1
    print (f' Tested decklist in {sum(durations)} ({sum(durations)/len(durations)} each)')

    # Return the average winning turn number
    return total_turns / num_trials
    
def run_epoch(deckrange, num_trials, max_turns):
    deck_baseline, decks_61, cards_61, decks_59, cards_59 = get_deck_variants(deckrange)
    wins_61 = {}
    wins_59 = {}
    
    for i in range(len(decks_61)):
        wins_61[i] = []
    for i in range(len(decks_59)):
        wins_59[i] = []
    print(f' Baseline decklist: {deck_baseline}')
    print(f' Number of 61-card decks: {len(decks_61)}')
    print(f' Number of 59-card decks: {len(decks_59)}')
    baseline_wins = test_decklist(deck_baseline, num_trials, max_turns)

    for i in range(num_trials):
        for deck_61_index, deck_61 in enumerate(decks_61):
            wins_61[deck_61_index].append(test_decklist(deck_61, num_trials, max_turns))
        for deck_59_index, deck_59 in enumerate(decks_59):
            wins_59[deck_59_index].append(test_decklist(deck_59, num_trials, max_turns))

        wins_61_avgs = {}
        wins_59_avgs = {}
        for deck_61_index, deck_61 in enumerate(decks_61):
            wins_61_avgs[cards_61[deck_61_index]] = sum(wins_61[deck_61_index]) / len(wins_61[deck_61_index])
        for deck_59_index, deck_59 in enumerate(decks_59):
            wins_59_avgs[cards_59[deck_59_index]] = sum(wins_59[deck_59_index]) / len(wins_59[deck_59_index])

        # Sort the wins_61_avgs and wins_59_avgs by average winning turn
        wins_61_avgs = {k: v for k, v in sorted(wins_61_avgs.items(), key=lambda item: item[1])}
        wins_59_avgs = {k: v for k, v in sorted(wins_59_avgs.items(), key=lambda item: item[1])}

        # Print out the sorted list of cards and their average winning turn
        print(f' Baseline wins: {baseline_wins}')
        print(f'  Best cards to add:')
        for card, avg_win in wins_61_avgs.items():
            delta = avg_win - baseline_wins
            if delta > 0:
                print(f'   {card}: +{delta}')
            else:
                print(f'   {card}: {delta}')
        print(f'  Best cards to remove:')
        for card, avg_win in wins_59_avgs.items():
            delta = avg_win - baseline_wins
            if delta > 0:
                print(f'   {card}: +{delta}')
            else:
                print(f'   {card}: {delta}')

        # Get the best card to add and the best card to remove
        best_card_to_add = list(wins_61_avgs.keys())[0]
        best_card_to_remove = list(wins_59_avgs.keys())[0]

        # Average the win rate of the best 61-card deck and the best 59-card deck
        best_61_win = wins_61_avgs[best_card_to_add]
        best_59_win = wins_59_avgs[best_card_to_remove]
        best_win = (best_61_win + best_59_win) / 2

        print (f' Best card to add: {best_card_to_add} ({best_61_win})')
        print (f' Best card to remove: {best_card_to_remove} ({best_59_win})')
        delta = best_win - baseline_wins
        print (f' Best win: {best_win} vs. {baseline_wins} ({delta})')

    return baseline_wins, best_win, best_card_to_add, best_card_to_remove


num_epochs = 100 # 1000
num_trials = 1000 # 10000
max_turns = 8 # 20

for i in range(num_epochs):
    print(f'Epoch {i+1} of {num_epochs}')
    baseline_wins, average_wins, card_to_add, card_to_sub = run_epoch(deckrange, num_trials, max_turns)
    
    # Find the card in deckrange that has this name and increase its quant
    for card in deckrange:
        if card['name'] == card_to_add:
            card['quant'] += 1
        if card['name'] == card_to_sub:
            card['quant'] -= 1

deck_baseline, decks_61, cards_61, decks_59, cards_59 = get_deck_variants(deckrange)
print(f'Final decklist:')
print(deck_baseline)
