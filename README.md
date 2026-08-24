# 0.2 BTC Puzzle

![0.2 BTC Puzzle](https://privatekeys.pw/images/puzzles/0.2-btc-puzzle.png)

This puzzle was created to challenge the community to identify the correct 12-word seed phrase from an image. The solution will unlock a Bitcoin wallet containing 0.2 BTC. The goal is to analyze the image, identify potential seed words, and test them against the targeted Bitcoin address: **1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ**.

## Purpose
This script helps users by allowing them to test only the words they identify from the image instead of testing against the entire BIP39 word list. This significantly increases the search speed by focusing only on the potential words.

## Instructions

Follow these steps to run the script:

1. **Clone the repository:**
    ```bash
    git clone https://github.com/panchpasha/0.2-BTC-Puzzle-script.git
    ```

2. **Navigate to the project directory:**
    ```bash
    cd 0.2-BTC-Puzzle-script
    ```

3. **Ensure you have Python and pip installed:**

    Install `bip-utils`:
    ```bash
    pip install bip-utils
    ```

4. **Create a text file named `seedwords.txt` in the project directory and add your identified seed words, separated by commas. For example:**
    ```txt
    moon,tower,food,real,black
    ```

5. **Run the script:**
    ```bash
    python3 check_seed_phrases.py
    ```

## Example Script Output

When you run the script, you will see output like this:

```bash
Starting the seed phrase checks...

Testing seed phrase: moon tower food real black subject time proof only win world face
Error: Invalid checksum (expected 1111, got 1010) with seed phrase: moon tower food real black subject time proof only win world face

Tested 5000 combinations so far.
Tested 10000 combinations so far.

Match found! Seed Phrase: moon tower food real black subject time proof only win world face => Address: 1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ
```

## Script Explanation

Below is the Python script included in this repository:

```bash
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
    
    except Exception as e:
        # Error handling and return None if the seed phrase is invalid
        print(f"Error: {e} with seed phrase: {seed_phrase}")  # Debugging output
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
```

## Hints
- **'Moon'** and **'Tower'** can be found on the clock's hands.
- **'Food'** can be found on the Seattle Space Needle.
- **'Breathe'** can be found on George Floyd's chest as well as the Statue's Neck.
- Rune 1 (Top Left) is in Russian: **"Я нaдeюcь чтo cюдa бyдyт пpиcылaть мнoгo биткoинoв"** and translates to **"I hope that many bitcoins will be sent here."**
- Rune 2 (Bottom Left) is in Russian: **"Cyммa двyx чиceл"** and translates to **"Sum of two numbers."**
- Rune 3 (Above Trump) is in Bill's Cipher and translates to **"Tuesday."**
- Rune 4 (Long on Right) is in Russian: **"Здecь зaшифpoвaны биткoины нa чёpный дeнь нoмep X"** and translates to **"Here are encrypted bitcoins for a rainy day number X."**
- **'This'** is likely a seed word, as it's repeated in **"This is the first prediction," "Fuck this shit,"** and **"Find the seed phrase in this picture."**
- **'Subject'** is underlined on the statue to the right.
- Using Forensically, or Photoshop, the base of the Statue of Liberty reveals **"Only Bitcoin"** under **"Only real Bitcoin,"** which likely means **'Real'** is a seed word.
- The Latin to the bottom right refers to **"The Pot Calling The Kettle Black,"** with **'Black'** also being repeated in references to the Black Lives Matter movement, so it's likely another word.
