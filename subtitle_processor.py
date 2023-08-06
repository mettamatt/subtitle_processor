# Standard library imports
import logging
import os
import sys
from collections import defaultdict

# Third party imports
import pysrt
import spacy

SPACY_MODEL = 'en_core_web_md' #en_core_web_sm, en_core_web_md, en_core_web_lg
MAX_READING_SPEED = 20
MAX_LINE_LENGTH = 42
MIN_DURATION = 1
MAX_DURATION = 6

DEBUG = False  # Set to True to enable debug logging

try:
    nlp = spacy.load(SPACY_MODEL)
except OSError:
    print(f'Downloading language model {SPACY_MODEL} for the spaCy POS tagger\n'
          "(don't worry, this will only happen once)")
    from spacy.cli import download
    download(SPACY_MODEL)
    nlp = spacy.load(SPACY_MODEL)

logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

def process_hyphenated_word(doc, idx, current_line_tokens):
    if idx < len(doc) - 1 and doc[idx + 1].text == '-':
        hyphenated_tokens = [doc[idx].text + doc[idx].whitespace_]
        idx += 1  # Move to the hyphen
        while idx < len(doc) and (doc[idx].text == '-' or doc[idx].is_alpha):
            hyphenated_tokens.append(doc[idx].text + doc[idx].whitespace_)
            idx += 1
        current_line_tokens.extend(hyphenated_tokens)
        return True, idx  # Return True indicating a hyphenated word was found, and the next idx
    return False, idx

def process_contraction(doc, idx, current_line_tokens, max_line_length):
    initial_idx = idx
    token_text = doc[idx].text
    contraction_tokens = [token_text + doc[idx].whitespace_]
    
    while idx + 1 < len(doc) and "'" in doc[idx + 1].text:
        idx += 1
        contraction_tokens.append(doc[idx].text + doc[idx].whitespace_)

    combined_text = ''.join(contraction_tokens)
    prospective_line_with_contraction = ''.join(current_line_tokens) + combined_text
    
    if len(prospective_line_with_contraction) <= max_line_length:
        current_line_tokens.extend(contraction_tokens)
        return False, idx  # False indicates the contraction wasn't moved to a new line
    
    return True, initial_idx  # True indicates the contraction was moved to a new line

def get_intelligent_breakpoints(phrase, max_line_length=42):
    phrase = phrase.strip()
    doc = nlp(phrase)
    current_line_tokens = []  # To keep track of the current line as tokens
    lines = []
    idx = 0

    while idx < len(doc):
        token = doc[idx]
        token_text = token.text

        # Check for hyphenated words
        hyphen_found, new_idx = process_hyphenated_word(doc, idx, current_line_tokens)
        if hyphen_found:
            idx = new_idx  # Adjust idx based on the returned value from process_hyphenated_word
            continue

        # Check for contractions using apostrophes
        if idx < len(doc) - 1 and "'" in doc[idx + 1].text:
            moved_to_next_line, idx = process_contraction(doc, idx, current_line_tokens, max_line_length)

            if moved_to_next_line:
                if current_line_tokens:
                    lines.append(''.join(current_line_tokens).strip())
                current_line_tokens = [token_text + token.whitespace_]
            idx += 1  # Move to the next token after processing the contraction
        else:
            # Prepare a prospective line addition
            prospective_line_tokens = current_line_tokens + [token_text + token.whitespace_]
            prospective_line = ''.join(prospective_line_tokens).strip()

            if len(prospective_line) <= max_line_length or token.dep_ == "punct":
                current_line_tokens.append(token_text + token.whitespace_)
                idx += 1
            else:
                if current_line_tokens:
                    lines.append(''.join(current_line_tokens).strip())
                current_line_tokens = [token_text + token.whitespace_]
                idx += 1

    if current_line_tokens:
        lines.append(''.join(current_line_tokens).strip())

    # Ensure that there are at most 2 lines
    while len(lines) > 2:
        lines[-2] += ' ' + lines[-1]
        del lines[-1]
        
    return [lines] if lines else []
    
def create_and_add_subtitle(lines, start_time, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start=None):    
    # Flatten list of lists into single list of strings
    flattened_lines = [item for sublist in lines for item in sublist]
    
    # Join lines together, but ensure that there are at most 2 lines
    phrase = "\n".join(flattened_lines)
    split_phrase = phrase.split('\n')
    while len(split_phrase) > 2:
        split_phrase[-2] += ' ' + split_phrase[-1]
        del split_phrase[-1]
    phrase = "\n".join(split_phrase)
    
    # calculate duration based on phrase length
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

    # return the new end time
    return new_end + pysrt.SubRipTime(milliseconds=1)

def integrity_check(original_text, adjusted_text):
    original_words = original_text.split()
    adjusted_words = adjusted_text.split()

    if original_words != adjusted_words:
        for i, (original_word, adjusted_word) in enumerate(zip(original_words, adjusted_words)):
            if original_word != adjusted_word:
                context_range = 5  # Number of words to include before and after the mismatch
                original_context = original_words[max(i - context_range, 0):min(i + context_range + 1, len(original_words))]
                adjusted_context = adjusted_words[max(i - context_range, 0):min(i + context_range + 1, len(adjusted_words))]
                logging.error(f"Integrity check failed at word {i}: Original word is '{original_word}', but adjusted word is '{adjusted_word}'.")
                logging.error(f"Original context: {' '.join(original_context)}")
                logging.error(f"Adjusted context: {' '.join(adjusted_context)}")
                return False
        if len(original_words) > len(adjusted_words):
            logging.error(f"Integrity check failed: Original text has additional words: {original_words[len(adjusted_words):]}")
            return False
        elif len(adjusted_words) > len(original_words):
            logging.error(f"Integrity check failed: Adjusted text has additional words: {adjusted_words[len(original_words):]}")
            return False
    else:
        logging.info("Integrity check passed: Original and adjusted texts match.")
        return True

def split_and_adjust_subtitles(input_file_path):    
    orig_subs = pysrt.open(input_file_path)
    new_subs = []
    unique_new_subtitles = set()
    orig_to_new_subs = defaultdict(list)
    
    # Collect Original Text
    original_text = " ".join(sub.text for sub in orig_subs)

    for i, sub in enumerate(orig_subs):
        # Process the entire subtitle text
        phrase = sub.text.replace('\n', ' ').strip()
        
        lines = get_intelligent_breakpoints(phrase, MAX_LINE_LENGTH)
        
        original_start = sub.start
        next_sub_start = orig_subs[i+1].start if i < len(orig_subs) - 1 else None

        # Process the lines generated from the subtitle
        if lines:
            original_start = create_and_add_subtitle(lines, original_start, new_subs, unique_new_subtitles, orig_to_new_subs, sub, i, next_sub_start)

    # Collect Adjusted Text
    adjusted_text = " ".join(new_sub.text for new_sub in new_subs)

    # Run the integrity check
    if not integrity_check(original_text, adjusted_text):
        logging.error("Integrity check failed: Original and adjusted texts do not match.")
    else:
        logging.info("Integrity check passed: Original and adjusted texts match.")

    # Save the adjusted subtitles
    subs = pysrt.SubRipFile(items=new_subs)
    output_file_path = os.path.splitext(input_file_path)[0] + '.adjusted.srt'
    subs.save(output_file_path, encoding='utf-8')

    logging.debug(f'[END] split_and_adjust_subtitles')
    return output_file_path, orig_to_new_subs
    
if __name__ == "__main__":
    # Check if command line argument is provided
    if len(sys.argv) < 2:
        print("Usage: python subtitle_processor.py /path/to/subtitle/file.srt")
        sys.exit(1)

    # Get the path to the .srt file from the command line arguments
    input_file_path = sys.argv[1]

    # Call the function to adjust the subtitles
    split_and_adjust_subtitles(input_file_path)
