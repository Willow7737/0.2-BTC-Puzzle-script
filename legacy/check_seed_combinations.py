import itertools
import random
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
import time

# Load the seed word list from a text file
with open("seedwords.txt", "r") as file:
    seed_words = [word.strip() for word in file.read().split(",")]

# Target Bitcoin address to check against (Legacy address format)
target_address = "1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ"

# Track start time and total combinations tested
start_time = time.time()
total_combinations_tested = 0
last_progress_time = time.time()

def generate_address_from_seed(seed_phrase):
    try:
        # Generate the seed from the mnemonic phrase
        seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
        
        # Generate the BIP44 wallet (Legacy address format)
        bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
        bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        
        # Return the legacy address
        return bip44_acc.PublicKey().ToAddress()
    
    except Exception:
        # Suppress detailed errors and continue
        return None

# Shuffle the word list for randomness
random.shuffle(seed_words)

# Initial output to confirm the script is running
print("Starting the seed phrase checks...")

# Generate all possible unique combinations of 12 seed words
for combination in itertools.permutations(seed_words, 12):
    seed_phrase = " ".join(combination)
    
    address = generate_address_from_seed(seed_phrase)
    
    if address is None:
        continue  # Skip to the next combination if there was an error
    
    total_combinations_tested += 1

    # Check if the generated address matches the target address
    if address == target_address:
        print(f"Match found! Seed Phrase: {seed_phrase} => Address: {address}")
        break

    # Print progress every 10 seconds
    if time.time() - last_progress_time >= 10:
        print(f"Tested {total_combinations_tested} combinations so far.")
        last_progress_time = time.time()

print(f"Finished checking {total_combinations_tested} combinations.")
