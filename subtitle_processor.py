# Standard library imports
import argparse
from collections import defaultdict
from itertools import zip_longest
import logging
import os
import sys

# Third-party imports
import pysrt
import spacy
from spacy.cli import download

# Spacy model configurations
# Available options: 'en_core_web_sm', 'en_core_web_md', 'en_core_web_lg'
SPACY_MODEL = 'en_core_web_md'

# Reading speed and line constraints
MAX_READING_SPEED = 20  # Characters per second
MAX_LINE_LENGTH = 42

# Duration constraints
MIN_DURATION = 1  # Minimum duration in seconds
MAX_DURATION = 6  # Maximum duration in seconds

try:
    nlp = spacy.load(SPACY_MODEL)
except OSError:
    logging.warning(f'Downloading language model {SPACY_MODEL} for the spaCy POS tagger. '
                    "Don't worry, this will only happen once.")
    download(SPACY_MODEL)
    try:
        nlp = spacy.load(SPACY_MODEL)
    except OSError:
        logging.error(f"Failed to load spaCy model {SPACY_MODEL} after downloading. Check your installation.")
        raise

logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

def process_hyphenated_word(doc, idx, current_line_tokens):
    """
    Process hyphenated words in a spaCy Doc object starting from the given index.
    
    Parameters:
    - doc: spaCy Doc object
    - idx: Current index in the doc
    - current_line_tokens: List of tokens for the current line being processed
    
    Returns:
    - processed (bool): True if a hyphenated word was found and processed, False otherwise
    - index (int): The next index to process in the doc
    """
    if idx < len(doc) - 1 and doc[idx + 1].text == '-':
        hyphenated_tokens = [doc[idx].text + doc[idx].whitespace_]
        idx += 1  # Move to the hyphen
        while idx < len(doc) and (doc[idx].text == '-' or doc[idx].is_alpha):
            hyphenated_tokens.append(doc[idx].text + doc[idx].whitespace_)
            idx += 1
        current_line_tokens.extend(hyphenated_tokens)
        return True, idx
    return False, idx

def process_contraction(doc, idx, current_line_tokens):
    """
    Process contractions in a spaCy Doc object starting from the given index.
    
    Parameters:
    - doc: spaCy Doc object
    - idx: Current index in the doc
    - current_line_tokens: List of tokens for the current line being processed
    
    Returns:
    - moved_to_new_line (bool): True if the contraction was moved to a new line, False otherwise
    - index (int): The next index to process in the doc
    """
    initial_idx = idx
    token_text = doc[idx].text
    contraction_tokens = [token_text + doc[idx].whitespace_]
    
    while idx + 1 < len(doc) and "'" in doc[idx + 1].text:
        idx += 1
        contraction_tokens.append(doc[idx].text + doc[idx].whitespace_)

    combined_text = ''.join(contraction_tokens)
    prospective_line_with_contraction = ''.join(current_line_tokens) + combined_text
    
    if len(prospective_line_with_contraction) <= MAX_LINE_LENGTH:
        current_line_tokens.extend(contraction_tokens)
        return False, idx  # False indicates the contraction wasn't moved to a new line
    
    return True, initial_idx  # True indicates the contraction was moved to a new line

def get_intelligent_breakpoints(phrase):
    """
    Splits a given phrase into lines based on certain conditions and a maximum line length.
    
    Parameters:
    - phrase: The text phrase to split
    
    Returns:
    A list of lines resulting from the intelligent splitting of the phrase.
    """
    phrase = phrase.strip()
    doc = nlp(phrase)
    current_line_tokens = []
    lines = []
    idx = 0

    while idx < len(doc):
        token = doc[idx]
        token_text = token.text

        # Check for hyphenated words
        hyphen_found, new_idx = process_hyphenated_word(doc, idx, current_line_tokens)
        if hyphen_found:
            idx = new_idx
            continue

        # Check for contractions using apostrophes
        if idx < len(doc) - 1 and "'" in doc[idx + 1].text:
            moved_to_next_line, idx = process_contraction(doc, idx, current_line_tokens)
            if moved_to_next_line:
                if current_line_tokens:
                    lines.append(''.join(current_line_tokens).strip())
                current_line_tokens = [token_text + token.whitespace_]
            idx += 1
        elif token.ent_type_:
            # Preserve named entities
            entity_text = token.ent_type_

            while idx < len(doc) and doc[idx].ent_type_ == entity_text:
                current_line_tokens.append(doc[idx].text + doc[idx].whitespace_)
                idx += 1
        else:
            prospective_line_tokens = current_line_tokens + [token_text + token.whitespace_]
            prospective_line = ''.join(prospective_line_tokens).strip()

            if len(prospective_line) <= MAX_LINE_LENGTH or token.dep_ == "punct":
                current_line_tokens.append(token_text + token.whitespace_)
                idx += 1
            else:
                if current_line_tokens:
                    lines.append(''.join(current_line_tokens).strip())
                current_line_tokens = [token_text + token.whitespace_]
                idx += 1

    if current_line_tokens:
        lines.append(''.join(current_line_tokens).strip())

    while len(lines) > 2:
        lines[-2] += ' ' + lines[-1]
        del lines[-1]

    return lines
    
def create_adjusted_subtitle(lines, start_time, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start=None):    
    """
    Creates a new adjusted subtitle and appends it to the new_subs list.

    Args:
    - lines (list): List of subtitle lines.
    - start_time (SubRipTime): Start time for the subtitle.
    - ... (Other arguments)
    
    Returns:
    - SubRipTime: New end time.
    """
    
    # Join lines together, but ensure that there are at most 2 lines
    phrase = "\n".join(lines)
    split_phrase = phrase.split('\n')
    while len(split_phrase) > 2:
        split_phrase[-2] += ' ' + split_phrase[-1]
        del split_phrase[-1]
    phrase = "\n".join(split_phrase)
    
    # Calculate duration based on phrase length
    duration_seconds = max(min(len(phrase) / MAX_READING_SPEED, MAX_DURATION), MIN_DURATION)
    duration_milliseconds = duration_seconds * 1000
    new_end = start_time + pysrt.SubRipTime(milliseconds=duration_milliseconds)

    # Check if the new_end time exceeds the start time of the next original subtitle.
    if next_sub_start is not None and new_end > next_sub_start:
        new_end = next_sub_start - pysrt.SubRipTime(milliseconds=1)
        
    new_sub = pysrt.SubRipItem(index=len(new_subs) + 1, text=phrase, start=start_time, end=new_end)
    new_sub_tuple = (new_sub.text, str(new_sub.start), str(new_sub.end))

    if new_sub_tuple not in unique_new_subtitles:
        new_subs.append(new_sub)
        unique_new_subtitles.add(new_sub_tuple)
        logging.debug(f'  Added new subtitle to list: "{new_sub.text}"')
    else:
        logging.debug(f'  Skipped adding subtitle as it already exists: "{new_sub.text}"')

    orig_to_new_subs[i].append(new_sub.text)

    # Return the new end time
    return new_end + pysrt.SubRipTime(milliseconds=1)

def integrity_check(original_text, adjusted_text, check_mode='immediate'):
    """
    Compares original and adjusted texts for equality based on the chosen check mode.

    Args:
    - original_text (str): The original text string.
    - adjusted_text (str): The adjusted text string.
    - check_mode (str): Type of integrity check - 'immediate' or 'detailed'. Default is 'immediate'.

    Returns:
    - bool: True if the texts match, otherwise False.
    """
    
    original_words = original_text.split()
    adjusted_words = adjusted_text.split()

    if check_mode == 'immediate':
        # Immediate check by comparing word lengths
        if len(original_words) != len(adjusted_words):
            logging.error("Integrity check failed: Word counts between original and adjusted texts do not match.")
            return False
        else:
            logging.info("Integrity check passed: Original and adjusted texts match.")
            return True

    elif check_mode == 'detailed':
        # Detailed word-by-word comparison
        for i, (original_word, adjusted_word) in enumerate(zip_longest(original_words, adjusted_words)):
            if original_word != adjusted_word:
                context_range = 5  # Number of words to include before and after the mismatch
                original_context = original_words[max(i - context_range, 0):min(i + context_range + 1, len(original_words))]
                adjusted_context = adjusted_words[max(i - context_range, 0):min(i + context_range + 1, len(adjusted_words))]
                logging.error(f"Integrity check failed at word {i}: Original word is '{original_word}', but adjusted word is '{adjusted_word}'.")
                logging.error(f"Original context: {' '.join(original_context)}")
                logging.error(f"Adjusted context: {' '.join(adjusted_context)}")
                return False
        logging.info("Integrity check passed: Original and adjusted texts match.")
        return True

    else:
        logging.error(f"Invalid check_mode '{check_mode}'. Please use 'immediate' or 'detailed'.")
        return False

def split_and_adjust_subtitles(input_file_path):
    """Adjusts the subtitles from the provided file based on predefined rules.

    Args:
    - input_file_path (str): Path to the original subtitle file.

    Returns:
    - tuple: Path to the adjusted subtitle file and a mapping from original to new subtitles.
    """
    
    original_subtitles = pysrt.open(input_file_path)
    new_subtitles = []
    unique_new_subtitles = set()
    original_to_new_mapping = defaultdict(list)
    
    # Collect Original Text
    original_text = " ".join(sub.text for sub in original_subtitles)

    for idx, subtitle in enumerate(original_subtitles):
        phrase = subtitle.text.replace('\n', ' ').strip()
        lines = get_intelligent_breakpoints(phrase)
        
        start_time = subtitle.start
        next_start_time = original_subtitles[idx+1].start if idx < len(original_subtitles) - 1 else None

        # Process the lines generated from the subtitle
        if lines:
            start_time = create_adjusted_subtitle(lines, start_time, new_subtitles, unique_new_subtitles, original_to_new_mapping, subtitle, idx, next_start_time)

    # Collect Adjusted Text
    adjusted_text = " ".join(new_sub.text for new_sub in new_subtitles)

    # Run the integrity check
    integrity_check(original_text, adjusted_text, 'detailed')
    
    output_path = os.path.splitext(input_file_path)[0] + '.adjusted.srt'
    adjusted_subtitles = pysrt.SubRipFile(items=new_subtitles)
    adjusted_subtitles.save(output_path, encoding='utf-8')

    return output_path, original_to_new_mapping
    
def main():
    parser = argparse.ArgumentParser(description='Adjust the subtitles of a given file.')
    parser.add_argument('input_file_path', type=str, help='Path to the subtitle file (.srt)')

    args = parser.parse_args()
    output_path, _ = split_and_adjust_subtitles(args.input_file_path)
    
    print(f"Adjusted subtitles saved to: {output_path}")

if __name__ == "__main__":
    main()
