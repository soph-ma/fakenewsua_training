import pandas as pd
import torch
import ast
import string
import pymorphy2
from collections import Counter
from nltk import sent_tokenize

# setup
csvfile = "translated.csv"

morph = pymorphy2.MorphAnalyzer(lang='uk')
with open(r'src/misc/stopwords_ua_list.txt', "r", encoding="utf-8") as f: 
    stopwords = ast.literal_eval(f.read())
with open("src/misc/markers.txt", "r", encoding="utf-8") as f:
    markers = [w.replace("\n", "") for w in f.readlines()[:100]]


def cat_titles_and_texts(titles: list[str], texts: list[str]) -> list[str]:
    output = []
    for title, text in zip(titles, texts): 
        try:
            if not text.startswith(title): 
               text = title + " " + text
        except: pass
        output.append(text)
    return output
    
def is_not_punctuation(word):
    return all(char not in string.punctuation for char in word)

def get_x(df: pd.DataFrame) -> list[str]: 
    x = []
    for index, row in df.iterrows():
        try: 
            text = row["ukr_text"]
        except KeyError: 
            text = row["Text"]
        x.append(text)
    return x

def get_x1(df: pd.DataFrame) -> list[str]:
    """Gets titles"""
    x1 = []
    for index, row in df.iterrows(): 
        try: 
            title = row["title_ukr"]
        except LookupError: # if no title take first sentence in a text as a title
            text = row["Text"]
            title = sent_tokenize(text)[0]
        x1.append(title)
    return x1

def get_y(df: pd.DataFrame) -> list[int]: # real = 0, fake = 1
    try: 
        y = df["label"]
    except KeyError: 
        y = df["Label"]
    nums = []
    for element in y: 
        if element == "Real" or element == True: nums.append(float(0))
        else: nums.append(float(1))
    return nums

def create_dictionary(x: list[str]) -> dict: 
    dictionary = dict()
    count = 1
    for text in x: 
        words = preprocess_text(text)
        for i, word in enumerate(words): 
            if word != 0: 
                if word not in dictionary: 
                    dictionary[word] = count 
                    count += 1
                else: 
                    words[i] = dictionary[word]
    return dictionary

def tokenize_x(x: list[str], dictionary: dict) -> list[list[float]]: 
    tokenized = []
    for text in x: 
        words = preprocess_text(text)
        for i, word in enumerate(words): 
            if word not in dictionary or word in markers or word in stopwords or not is_not_punctuation(word): 
                words[i] = 0
            else:
                words[i] = dictionary[word]
        tokenized.append(words)
    return tokenized

def tokenize_titles(titles: list[str], dictionary: dict) -> list[list[float]]: 
    tokenized = []
    for title in titles: 
        words = preprocess_titles(title)
        for i, word in enumerate(words): 
            if word not in dictionary or word in markers or word in stopwords or not is_not_punctuation(word): 
                words[i] = 0
            else:
                words[i] = dictionary[word]
        tokenized.append(words)
    return tokenized

def lemmatize_word(word):
    return morph.parse(word)[0].normal_form


def bert_tokenize_without_masks(x: list[str], tokenizer) -> (torch.Tensor): 
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
        
    tokenized_x = []
    for text in x:
        encoded_dict = tokenizer.encode_plus(
            text,                      
            add_special_tokens = True, 
            max_length = 150,          
            truncation = True,
            padding = 'max_length',    
            return_tensors = 'pt',     
        )
        
        tokenized_x.append(encoded_dict['input_ids'].to(device))
        
    # flatten the lists
    tokenized_x = torch.cat(tokenized_x, dim=0)
    
    return tokenized_x


def get_vocab_size(texts: list[str]): 
    all_texts = ""
    for t in texts:
        try:
            all_texts += (t + " ")
        except: pass
    vocab_size = len(set(all_texts.lower().split()))
    return vocab_size


def preprocess_text(text: str, padding=150) -> list[str]: 
    # lemmatization and removing stop words
    text = str(text)
    words = [lemmatize_word(word) for word in text.split() if word.lower() not in stopwords]
    padded = words[:padding] + [0] * (padding - len(words))
    return padded

def balance_data(df): 

    label_col = 'Label' if 'Label' in df.columns else 'label'
    fake_label = False if 'Label' in df.columns else 'Fake'
    real_label = True if 'Label' in df.columns else 'Real'

    try:
        num_fake = (df['Label'] == False).sum()
    except: num_fake = (df['label'] == "Fake").sum()
    try:
        num_real = (df['Label'] == True).sum()
    except:
        num_real = (df['label'] == "Real").sum()


    if num_real > num_fake:
        real_indices = df[df[label_col] == real_label].index
        sampled_real_indices = pd.DataFrame(real_indices).sample(n=num_fake, random_state=42).index
        print(sampled_real_indices)
        df_balanced = df.loc[sampled_real_indices.union(df[df[label_col] == fake_label].index)]
    else:
        df_balanced = df
    return df_balanced

def get_average_length(x: list[str]): 
    lengths = []
    for text in x: 
        try:
            words = [lemmatize_word(word) for word in text.split() if word.lower() not in stopwords]
            lengths.append(len(words))
        except: lengths.append(0)
    length_counts = Counter(lengths)
    most_common_lengths = length_counts.most_common()
    print(most_common_lengths)
    return sum(lengths) / len(lengths)
    