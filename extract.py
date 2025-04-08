#!/usr/bin/env python

# Environment: gartenlaube
# Befehl: python3 extract.py > test.txt

from collections import defaultdict
import requests
from bs4 import BeautifulSoup
import re
import os
import csv
import json
from tqdm import tqdm
import argparse
import nltk
from nltk.tokenize import word_tokenize

class GartenlaubeExtractor:
    def __init__(self, S, URL, black_list = set()):
        """
        Constructor of the class GartenlaubeExtractor.

        @params
            S: session
            URL: wikiAPI-URL
            black_list: titles of works that should not be scraped
        """
        self.S = S
        self.URL = URL
        self.black_list = black_list
        self.reordered_titles = set()
        self.genre = dict()
        self.text_dict = defaultdict(dict)
        self.corpus = []
        self.subcat = []
        self.max_id = 0
        self.metadata_list = []
        self.meta_dict = defaultdict(dict)
        self.names = defaultdict(list)
        self.nschatz = self.novellenschatz()
        self.fieldnames = []
        
        # lists of names to split author names in first- and lastname
        for file in tqdm(os.listdir("./resources/names"), desc="Processing name lists"):
            if file.endswith(".json"):
                key = file[:-5]
                with open(f"./resources/names/{file}", "r", encoding="utf-8") as f:
                    self.names[key] = json.load(f)

        # Exclude texts from the black_list folder
        for file in tqdm(os.listdir("./resources/black_list"), desc="Processing black_list files"):
            self.filter_blacklist("./resources/black_list/"+file)

    # Scraping
    def get_subcats(self):
        """
        This function retrieves a list of subcategories of the Gartenlaube. Each subcategory represents one year.
        """
        # cmlimit is 100, because there are 53 subcats
        PARAMS = {
        "action": "query",
        "cmtitle": "Kategorie:Die Gartenlaube",
        "list": "categorymembers",
        "format": "json",
        "cmlimit": "100",
        "cmtype": "subcat",
        }

        DATA = self.scrape_API(PARAMS)

        # List of the subcat directories
        self.subcats = DATA["query"]["categorymembers"]
    
    def scrape_API(self, params):
        """
        This method is a helpers-function to scrape the wiki-API.

        @params params: dictionary with parameters that should be used to scrape the API
        @returns DATA: a json-object with the results of the API-search
        """
        R = self.S.get(url=self.URL, params=params)
        DATA = R.json()
        return DATA
    
    # Text
    def get_text_metadata(self, subcat):
        """
        This method extracts the whole text of the Gartenlaube editions.

        @param subcat: current year of the Gartenlaube
        """
        ARTICLEPARAMS = {
        "action": "query",
        "cmtitle": subcat["title"]+" Artikel",
        "list": "categorymembers",
        "format": "json",
        "cmlimit": "1000",
        }
        ARTICLEDATA = self.scrape_API(ARTICLEPARAMS)

        ARTICLES = ARTICLEDATA['query']['categorymembers']

        if ARTICLES != []:
            # parse pages
            for page in tqdm(ARTICLES, desc="Extracting text and metadata"):
                WHOLE_PARAMS = {
                    "action": "parse",
                    "pageid": page["pageid"] ,
                    "prop": "text|wikitext",
                    "format": "json",
                }

                WHOLE_DATA = self.scrape_API(WHOLE_PARAMS)

                title = WHOLE_DATA["parse"]["title"] 

                # Split check for Blacklist and section
                extract_text = False
                genre = self.get_genre(title) 
                if genre != "":
                    extract_text = True

                # splitted because of high complexity
                if extract_text:
                    extract_text = self.match_blacklist_titles(title)

                if extract_text:
                    self.max_id += 1
                    # get whole text and episode splits
                    text = self.get_page_text_html(WHOLE_DATA["parse"]["text"]["*"])

                    if text != "":
                        self.text_dict[self.max_id] = {\
                            "whole": text,\
                            "episodes": self.split_episodes(text)\
                        }

                        # get metadata
                        serial = False
                        if len(self.text_dict[self.max_id]["episodes"]) > 1:
                            serial = True
                        self.meta_dict[self.max_id] = self.extract_metadata(serial, genre)

    def get_page_text_html(self, html):
        """
        This method extracts the text from the html page.

        @param html: html containing the text
        @returns text: text in the html
        """
        soup = BeautifulSoup(html, 'html.parser')

        all_text = soup.get_text().strip().split("\n")
        text = ""
        if self.match_blacklist_titles(all_text[all_text.index("Titel:")+1]):
        #if all_text[all_text.index("Titel:")+1] not in self.black_list:

            if "Indexseite" in all_text:

                # store unparsed metadata
                self.metadata_list = all_text[:all_text.index("Indexseite")+1]
                
                # store text
                text_content = all_text[all_text.index("Indexseite")+1:]
                # remove tabs
                text_content = [text.replace("\xa0", " ") for text in text_content]
                # remove image captions
                text_content = self.remove_img_captions(soup, text_content)

                # enumerate footnotes in the text
                footnotes = [item for item in text_content if item.startswith("↑")]
                if len(footnotes) < 0 and "Anmerkungen (Wikisource)" in text_content:
                    footnotes = text_content[text_content.index("Anmerkungen (Wikisource)")+1:]
                    text_content[text_content.index("Anmerkungen (Wikisource)")+1:] = self.count_footnotes(footnotes)
                elif len(footnotes) > 0 and not "Anmerkungen (Wikisource)" in text_content:
                    start_idx = text_content.index(footnotes[0])
                    text_content[start_idx:] = self.count_footnotes(footnotes)


                text = "\n".join(text_content).strip()
        
        return text
    
    def split_episodes(self, text):
        """
        This method splits the given text into episodes.

        @params 
            title: title of the text
            text: string containing the whole text
        @returns episodes: list where each item is one episode of the text
        """
        prev_page = 0
        curr_page = 0
        episodes = []
        out_text = ""

        for line in text.split("\n"):
            # page number
            match = re.match(r"\[(\d+)\]", line)

            if match:
                curr_page = int(match.group(1))

                if prev_page == 0:
                    prev_page = curr_page - 1
                
                if curr_page == prev_page + 1:
                    out_text += line
                    out_text += "\n"
                    prev_page = curr_page
                else:
                    episodes.append(out_text)
                    out_text = line
                    out_text += "\n"
                    prev_page = curr_page
            else:
                out_text += line
                out_text += "\n"

        episodes.append(out_text)

        return episodes
    
    def remove_img_captions(self, soup, text_content):
        """
        This method removes the image captions from the text.

        @params
            soup: Beautifoulsoup-parser for the current page
            text_content: list with the text contents
        @returns text_content: text contents without image captions
        """
        for img in soup.find_all("img"):
            img_caption = img.next_element.text.strip()
            if img_caption != "":
                if img_caption in text_content:
                    text_content.remove(img_caption)
                else:
                    # closer inspection
                    no_tab_space_caption = re.sub(r"[\xa0 ]", "", img_caption)
                    found_elem = ""
                    for elem in text_content:
                        orig_elem = elem
                        if re.sub(r"[\xa0 \[\]\d]", "", elem) == no_tab_space_caption:
                            found_elem = orig_elem
                        
                    if found_elem != "":
                        text_content.remove(found_elem)
        return text_content
    
    def count_footnotes(self, footnotes):
        """
        This method adds a counter to the footnotes.

        @param footnotes: List of footnotes in the text
        @returns footnotes: List of footnotes with counter  
        """
        counter = 0
        for i in range(len(footnotes)):
            if footnotes[i] != '':
                footnotes[i] = f"{counter+1}. {footnotes[i]}"
                counter += 1
        return footnotes
    
    # Metadata 
    def extract_metadata(self, serial = False, genre = ''):
        """
        This method stores the metadata in a dictionary that represents the corpus.

        @param serial: True if text has more than one episode
        @returns metas: dictionary with the metadata for the current page
        """
        # initiale keys from corpus fields
        metas = {field: "" for field in self.fieldnames}

        # raw document id without episode index
        metas["Dokument ID"] = self.add_zeros(self.max_id, 5)

        # author
        author_names = self.metadata_list[self.metadata_list.index("Autor:")+1].strip().split(" ")
        if author_names != [""]:
            for name in author_names:
                if name in self.names["vornamen_w"]:
                    metas["Vorname"] += name+" "
                    metas["Gender"] = "f"
                elif name in self.names["vornamen_m"]:
                    metas["Vorname"] += name+" "
                    metas["Gender"] = "m"
                elif name in self.names["nachnamen"]:
                    metas["Nachname"] += name+" "
                else:
                    # Defaultsplit: Last name in the list is stored as last name, the rest as first name 
                    if author_names.index(name) != len(author_names)-1:
                        metas["Vorname"] += name
                        metas["Vorname"] += " "
                    else:
                        metas["Nachname"] += name
            metas["Vorname"] = metas["Vorname"].strip()
            metas["Nachname"] = metas["Nachname"].strip()
        else:
            metas["Vorname"] = "o.N."
            metas["Nachname"] = "o.N."

        if metas["Vorname"] not in ["o.N.", "unbekannt"] or metas["Nachname"] not in ["o.N.", "unbekannt"]:
            for item in scraper.corpus:
                if metas["Vorname"] == item["Vorname"] and metas["Nachname"] == item["Nachname"] and item["Kanon_Status"]!="":
                    metas["Kanon_Status"] = item["Kanon_Status"]

        # pages
        number_pages = re.sub(r"\xa0", "", self.metadata_list[self.metadata_list.index("aus:")+1].strip())
        match_num_page = re.search(r"Heft(.*), S\.(.*)", number_pages)
        if match_num_page:
            metas["Seiten"] += match_num_page.group()

            # position in the journal (only detects page number 1)
            if re.match(r"^1\b", match_num_page.group(2)):
                metas["Nummer im Heft (ab 00797: 1 erste Position. 0 nicht erste Position)"] = 1

        # seriality
        if serial:
            metas["seriell"] = "TRUE"
        else:
            metas["seriell"] = "FALSE"

        metas["Titel"] = self.metadata_list[self.metadata_list.index("Titel:")+1].strip()
        metas["Jahr_ED"] = self.metadata_list[self.metadata_list.index("Erscheinungsdatum:")+1].strip()
        metas["entstanden"] = self.metadata_list[self.metadata_list.index("Entstehungsdatum:")+1].strip()
        metas["Medium_ED"] = "Die Gartenlaube"
        metas["Medientyp_ED"] = "Familienblatt"
        metas["Hg."] = self.metadata_list[self.metadata_list.index("Herausgeber:")+1].strip()
        metas["in_Pantheon"] = "FALSE"
        metas["Verantwortlich_Erfassung"] = "GartenlaubeExtractor"
        metas["falls andere Quelle"] = f"wikisource | https://de.wikisource.org/wiki/{'_'.join(metas['Titel'].split(' '))}"

        if metas["Titel"] in self.nschatz:
            metas["in_Deutscher_Novellenschatz_(Heyse)"] = "TRUE"
        else:
            metas["in_Deutscher_Novellenschatz_(Heyse)"] = "FALSE"

        metas["Gattungslabel_ED"] = genre 

        metas["Gattungslabel_ED_normalisiert"] = self.get_normalized_genre(genre) 

        return metas
    
    def get_normalized_genre(self, genre: str):
        """
        This method returns the normalized label for the extracted genre.

        @param genre: string containing the extracted genre
        @returns v: normalized genre label
        """
        normalized_genre = {
            "Geschichte": "XE",
            "Begebenheit": "XE",
            "Novelle": "N",
            "Erzählung": "E",
            "Roman": "R",
            "Märchen": "M",
            "E_N_Rubrik": "E_N_Rubrik"
        }
        
        for k,v in normalized_genre.items():
            if k.lower() in genre.lower():
                return v
        return ''

    def novellenschatz(self):
        """
        This method extracts the titles in the Deutsche Novellenschatz to check whether the text is contained in it.

        @returns titles: list of the titles in the Deutsche Novellenschatz
        """
        titles = []
        for file in tqdm(os.listdir("./resources/nschatz_deu/data"), desc = "Processing Deutscher Novellenschatz"):
            with open(f"./resources/nschatz_deu/data/{file}", "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "xml")
                titles.append(soup.title.text)
        return titles

    # Black list
    def filter_index_type(self, subcat):
        """
        This function gets every index page and collects the names of the poems and ballades.

        @param subcat: current edition of the Gartenlaube
        """
        # Genres that should be extracted
        genres = ["Geschichte", "Begebenheit", "Novelle", "Erzählung", "Roman", "Märchen"]

        # Get all pages related to the subcategories (= pages for each year)
        FILTERPARAMS = {
            "action": "query",
            "cmtitle": subcat["title"],
            "list": "categorymembers", # allpage ausprobieren
            "format": "json",
            "cmlimit": "500",
            "cmnamespace": "0"
        }

        FILTERDATA = self.scrape_API(FILTERPARAMS)

        filter_pages = FILTERDATA["query"]["categorymembers"]
        
        if filter_pages != []:

            for page in filter_pages:
                RAWPARAMS = {
                    "action": "parse",
                    "pageid": page["pageid"] ,
                    "prop": "text",
                    "format": "json",
                }
                RAWDATA = self.scrape_API(RAWPARAMS)

                html = RAWDATA["parse"]["text"]["*"]

                soup = BeautifulSoup(html, 'html.parser')

                tables = soup.find_all('table')

                for table in tables:
                    if table:
                        if table.find('th') and table.find('th').text.strip() == "Autor":
                            for row in table.tbody.find_all('tr'):  
                                # Find all data for each column
                                columns = row.find_all('td')
                                # Geschichte, Begebenheit: XE
                                # Novelle: N
                                # Erzählung: E
                                # Roman: R
                                # Märchen: M
                                # TODO: Link zur Seite gleich mit aufnehmen
                                titles = [td.a["title"] for td in columns if td.a and (("class" in td.a.attrs and not td.a["class"][0].startswith("prp")) or "class" not in td.a.attrs)]
                                genre_type = ''  
                                title = ''                         
                                if len(columns) > 1 and titles != []:
                                    title = titles[0]
                                    genre_type = columns[-1].text.strip()
                                
                                if genre_type != '' and title != '': # TODO: Fix Historische Erzählung wird nicht erkannt
                                    if genre_type in ["Gedicht", "Ballade"]:
                                        #print("poem", columns)
                                        self.black_list.add(title) 
                                    else:
                                        # for testing
                                        i = 0
                                        found = False
                                        while i < len(genres):
                                            genre = genres[i]
                                            if genre.lower() in genre_type.lower():
                                                self.add_genre(title, genre_type)
                                                found = True
                                                i = len(genres)
                                            i += 1

                                        if found == False and genre_type not in ["Schluß", "Sechster BriefDas Wasser", "Illustrirte Reiseskizze", "Illustirte Reiseskizze", "M. R."]:
                                            print(genre_type) #for testing purposes 

    def filter_bookindex_genre(self, subcat):
        FILTERPARAMS = {
            "action": "query",
            "cmtitle": subcat["title"],
            "list": "categorymembers", # allpage ausprobieren
            "format": "json",
            "cmlimit": "500",
            "cmnamespace": "104" # 14: Artikel und Heftkategorien, 0: pages, 102: Seiten, 104: Index
        }

        FILTERDATA = self.scrape_API(FILTERPARAMS)

        filter_pages = FILTERDATA["query"]["categorymembers"]
        genre = ""
        if filter_pages != []:
            for page in filter_pages:
                RAWPARAMS = {
                    "action": "parse",
                    "pageid": page["pageid"] ,
                    "prop": "text|wikitext",
                    "format": "json",
                }
                RAWDATA = self.scrape_API(RAWPARAMS)

                #<p>Buchinhaltsverzeichnis:\n<a href="/wiki/Seite:Die_Gartenlaube_(1853)_p_003.jpg" class="prp-pagequality-4 quality4" title="Seite:Die Gartenlaube (1853) p 003.jpg">III</a>\n<a href="/wiki/Seite:Die_Gartenlaube_(1853)_p_004.jpg" class="prp-pagequality-4 quality4" title="Seite:Die Gartenlaube (1853) p 004.jpg">IV</a>\n</p>
                html = RAWDATA["parse"]["text"]["*"]

                soup = BeautifulSoup(html, 'html.parser')
                index_p = None
                i = 0

                index_pointers = ["Buchinhaltsverzeichnis", "Inhaltsverzeichnis"]
                while not index_p and i < len(index_pointers):
                    index_p = soup.find(lambda tag: tag.name == "p" and index_pointers[i] in tag.text)
                    i += 1

                if index_p:
                    bl_candidate = False

                    index_titles = [a["title"] for a in index_p.find_all("a")]
                    for title in index_titles: 
                        INDEXPARAMS = {
                            "action": "parse",
                            "page": title,
                            "prop": "text",
                            "format": "json",
                        }

                        INDEXDATA = self.scrape_API(INDEXPARAMS)
                        index_soup = BeautifulSoup(INDEXDATA['parse']['text']['*'], 'html.parser')
                        tables = index_soup.find_all('table')
                        
                        if tables:
                            if "1870" in INDEXPARAMS["page"]:
                                table = tables[1]
                            else:
                                table = tables[-1] 

                            # go through each row in the table
                            for tr in table.tbody.find_all("tr"):
                                if tr.find("th"):
                                    # Parse Section titles
                                    if tr.find("th").text.strip() != "" and "Novelle" in tr.find("th").text:
                                        bl_candidate = False

                                        if tr.find("th").text.strip() == "Erzählungen und Novellen.":
                                            genre = "E_N_Rubrik"
                                        else:
                                            genre = tr.find("th").text.strip() + "_Rubrik"
                                    else:
                                        bl_candidate = True
                                else:
                                    # Parse article titles
                                    # Gartenlaube 1868, p. 4 is structured as a list and not as a table
                                    tds = tr.find_all("td")  
                                    if len(tds) >= 2 and "align" not in tds[0].attrs:
                                        # Das zweite Element in tds ist die Seitenzahl für diesen Jahrgang. Kann auch für die Blacklistzuordnung genutzt werden.
                                        number_pattern = r"^\d+\."
                                        title = re.sub(number_pattern, "", tds[0].text.strip()).strip().lower()
                                        
                                        if title != "":  
                                            reordered_title = self.reorder_title(title)
                                            if bl_candidate and self.get_genre(title) == '':
                                                self.black_list.add(title)
                                                self.reordered_titles.add(reordered_title)
                                            else:
                                                if genre != "":
                                                    self.add_genre(title, genre, reordered_title) 
                                    else:
                                        if ("colspan" in tds[0].attrs or "align" in tds[0].attrs) and tds[0].text.strip() != '':
                                            if "Novelle" in tds[0].text:
                                                bl_candidate = False
                                                if tds[0].text.strip() == "Erzählungen und Novellen.":
                                                    genre = "E_N_Rubrik"
                                                else:
                                                    genre = tds[0].text.strip() + "_Rubrik"
                                            else:
                                                bl_candidate = True
                        else:
                            head_elem = index_soup.find('b')
                            for elem in head_elem.find_all_next(["li", 'b']):
                                if elem.name == 'b':
                                    if "Novelle" in elem.text:
                                        bl_candidate = False
                                        genre = elem.text.strip()
                                        if elem.text.strip() == "Erzählungen und Novellen.":
                                            genre = "E_N_Rubrik"
                                        else:
                                            genre = elem.text.strip() + "_Rubrik"
                                    else:
                                        bl_candidate = True
                                elif elem.name == "li":
                                    # Page numbers are added to the list item in this case
                                    number_pattern = r"(^\d+\.|\d+\.?$)"
                                    title = re.sub(number_pattern, "", elem.text.strip()).strip().lower()

                                    if title != "":
                                        reordered_title = self.reorder_title(title)
                                        if bl_candidate and self.get_genre(title) == '':
                                            self.black_list.add(title)
                                            self.reordered_titles.add(reordered_title)
                                        else:
                                            self.add_genre(title, genre, reordered_title)   

    def filter_blacklist(self, filename):
        """
        This method filters all texts that are in the lists in the black_list folder.

        @param filename: name of the black_list csv file
        """
        with open(filename, "r", encoding = "utf-8") as csv_file:
            corpus_reader = csv.DictReader(csv_file, delimiter = ";")

            for row in corpus_reader:
                # Add Title to Black list
                if row["Titel"] != '':
                    self.black_list.add(row["Titel"].lower())
                
                # Extract important corpus information
                if filename == "./resources/black_list/Bibliographie.csv":
                    if self.fieldnames == []:
                        self.fieldnames = row.keys()

                    self.corpus.append({"Vorname": row["Vorname"], "Nachname": row["Nachname"], "Kanon_Status": row["Kanon_Status"]})

                    # Store max idx while we are here
                    curr_id = int(re.match(r"0*(\d{1,})-\d+", row["Dokument ID"]).group(1))
                    if curr_id > self.max_id:
                        self.max_id = curr_id

    def reorder_title(self, bl_title):
        """
        This method fixes the order of the titles in the blacklist.

        @param bl_title: a title from the blacklist
        """
        # the titles in the wikisource genre list are reordered -> "Herr, der alte" instead of "Der alte Herr"
        order_match = re.search(r"([ \-’\w]+), ([\w ]+)([,\.] (.*)|)", bl_title)
        reordered_title = ""
        if order_match:
            reordered_title = order_match.group(2) + " " + order_match.group(1)
            if order_match.group(4):
                reordered_title += " " + order_match.group(4)
        return reordered_title

    def match_blacklist_titles(self, title):
        '''
        This method checks if a title is contained in the black list by exact match and word overlap.

        @param title: title of the page
        @returns False if the title is contained in the black_list.
        '''
        # exact match with the title and reordered titles
        title = title.lower()
        clean_title = re.sub(r" \(.*gartenlaube.*\)", "", title)
        if clean_title not in self.black_list and clean_title not in self.reordered_titles:
            title_tokens = set(word_tokenize(clean_title))

            for bl_title in self.black_list:
                bl_title = re.sub(r" \(.*gartenlaube.*\)", "", bl_title)
                bl_tokens = set(word_tokenize(bl_title))
                intersected_toks = title_tokens.intersection(bl_tokens)

                # min_len = 3
                # if len(title_tokens) < min_len:
                #     min_len = len(title_tokens)

                # if len(bl_tokens) < min_len and len(bl_tokens) > 0:
                #     min_len = len(bl_tokens)

                # if len(intersected_toks) >= min_len:
                #     return False
                if len(intersected_toks) > len(bl_tokens) * 0.9 or len(intersected_toks) > len(title_tokens) * 0.9:
                    return False
        else:
            return False

        return True
    
    def get_genre(self, title):
        '''
        This method checks if a title is contained in the category dictionary by exact matches and word overlap.

        @param title: title of the article
        @returns category of the article or empty string
        '''
        # exact match with the title and reordered titles
        title = title.lower()
        clean_title = re.sub(r" \(die gartenlaube \d+.*\)", "", title)
        found_genre = ""

        for (index_title, reordered_title), genre in self.genre.items():
            if clean_title == index_title or clean_title == reordered_title:
                return genre
            else:
                #word overlap
                title_tokens = set(word_tokenize(clean_title))
                index_tokens = set(word_tokenize(index_title))
                intersected_toks = title_tokens.intersection(index_tokens)


                if len(intersected_toks) > len(index_tokens) * 0.9 or len(intersected_toks) > len(title_tokens) * 0.9:
                    found_genre = genre
        return found_genre

    def add_genre(self, title: str, new_genre: str, reordered_title: str = ''):
        """
        This method adds title and genre to the genre list.

        @params
            title: title of the text
            new_genre: genre that should be added
            reordered_title: title with the corrected word order
        """
        title = title.strip().lower()
        genre = self.get_genre(title)

        if genre == "":
            self.genre[(title, reordered_title)] = new_genre
        elif genre != new_genre:
            if ("Novelle" in new_genre or "Erzählung" in new_genre) and genre == "E_N_Rubrik":
                self.genre[(title, reordered_title)] = new_genre     

    # Output
    def store_text(self):
        """
        This method stores the whole text and the episodes in txt-files.
        """
        for idx, texts in tqdm(self.text_dict.items(), desc="Creating text files"):
            file_title = self.meta_dict[idx]["Titel"]
            # reorder information in the title to match corpus file names
            match = re.match(r"([\w ’\"„“’\.\-,]+)(\(Die Gartenlaube (\d+)(/\d+)?\))?",file_title)
            if match:
                # title
                file_title = match.group(1).strip()

                # Year and name of the medium
                if match.group(3):
                    file_title += " " + match.group(3) + " "
                if match.group(2):
                    file_title += " Die Gartenlaube"

            # replace space with underscore
            file_title = re.sub(r"[ \-]", "_", file_title)
            file_title = re.sub(r"\W", "", file_title)
            file_title = re.sub(r"_{2,}", "_", file_title)
            file_title = re.sub(r"^_", "", file_title)

            raw_id = self.meta_dict[idx]["Dokument ID"]

            # get number of episodes
            num_episodes = len(texts["episodes"])

            # the episode-id should at least have lenght 2 (e.g. 01)
            id_len = 2
            # if there are more than 100 episodes, we need to adjust the length of the episode ids
            if len(str(num_episodes)) > id_len:
                id_len = len(str(num_episodes))

            # whole text filename
            filename= f"{raw_id}-{self.add_zeros(0, id_len)}_{file_title}"

            # store whole text
            with open(f"./output/whole_texts/{filename}.txt", "w", encoding = "utf-8") as out_file:
                out_file.write(texts["whole"])
            
            # store episode
            if num_episodes > 1:
                for i in range(num_episodes):
                    # episode filename
                    filename = f"{raw_id}-{self.add_zeros(i+1, id_len)}_{file_title}"
                    with open(f"./output/episodes/{filename}.txt", "w", encoding = "utf-8") as out_file:
                        out_file.write(texts["episodes"][i])
    
    def store_metadata(self):
        """
        This method appends the extracted metadata to the corpus.
        """        
        with open("./resources/black_list/Bibliographie.csv", "a", encoding = "utf-8") as csv_file:
        #with open("./resources/black_list/Bibliographie_TEST.csv", "w", encoding = "utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames, delimiter=";")
            # Remove comment when testing 
            #writer.writeheader()

            for idx, row in tqdm(self.meta_dict.items(), desc="Adding metadata to the corpus"):
                raw_id = row["Dokument ID"][:5]
                all_pages = row["Seiten"]

                num_episodes = len(self.text_dict[idx]["episodes"])

                # the episode-id should at least have lenght 2 (e.g. 01)
                id_len = 2
                # if there are more than 100 episodes, we need to adjust the length of the episode ids
                if len(str(num_episodes)) > id_len:
                    id_len = len(str(num_episodes))

                # whole text row
                row["Dokument ID"] = f"{raw_id}-{self.add_zeros(0, id_len)}"
                writer.writerow(row)
                
                # episode rows
                if num_episodes > 1:
                    page_match = re.search(r"Heft(.*), S\.(.*)", all_pages)
                    pages = []

                    if page_match:
                        if ';' in page_match.group(2):
                            pages = page_match.group(2).split(";")
                        elif "," in page_match.group(2):
                            pages = page_match.group(2).split(",")
                        elif "und"  in page_match.group(2):
                            pages = page_match.group(2).split("und")

                    for i in range(num_episodes):
                        row["Dokument ID"] = f"{raw_id}-{self.add_zeros(i+1, id_len)}"

                        if i < len(pages):
                            row["Seiten"] = pages[i].strip()
                        else:
                            row["Seiten"] = all_pages
                        writer.writerow(row)

    def store_dicts(self, text_dict, meta_dict):
        '''
        This method stores the text_dict and the meta_dict in a json file.

        @params
            text_dict: Dictionary with the whole texts and the episode texts.
            meta_dict: Dictionary containing the metadata for the extracted texts.
        '''
        with open("./test_dicts.json", "w", encoding="utf-8") as param_file:
            json.dump([text_dict, meta_dict], param_file)
    
    def add_zeros(self, num: int, new_len: int):
        """
        This method adds zeros at the front of a number.

        @params
            num: number that the zeros are added to
            new_len: length of the new number string
        @returns new: number string with zeros in front 
        """
        new = str(num)
        while len(new) < new_len:
            new = "0" + new
        return new


if __name__ == "__main__":
    nltk.download("punkt")
    nltk.download('punkt_tab')
    # CLI
    parser = argparse.ArgumentParser(prog='gartenlaube extractor')
    parser.add_argument('--modus', '-m', help='enable test modus with calling -m test', default="run")
    parser.add_argument('--processing', '-p', help='process code fast or safe', default="fast")
    parser.add_argument('--start', '-s', help='run code only for the journals after the start index (inclusive); start at 0', default=0)
    parser.add_argument('--end', '-e', help='run code only until the journal with the end index (exclusive)', default=None)

    modus = parser.parse_args().modus
    processing = parser.parse_args().processing
    start = int(parser.parse_args().start)
    end = parser.parse_args().end
    if end:
        end = int(end)


    if modus != "run" and not os.path.exists("./test_dicts.json"):
        modus = "run"

    # Create output-directory if needed
    if not os.path.isdir("./output/"):
        os.mkdir("./output")
    if not os.path.isdir("./output/episodes/"):
        os.mkdir("./output/episodes")
    if not os.path.isdir("./output/whole_texts/"):
        os.mkdir("./output/whole_texts")

    S = requests.Session()

    URL = "https://de.wikisource.org/w/api.php"

    scraper = GartenlaubeExtractor(S, URL)

    if modus == "run":
        # Programm ausführen
        scraper.get_subcats()
        all_text_dicts = dict()
        all_metadata = dict()
        saved_idx = 0 
        
        try: 
            for subcat in tqdm(scraper.subcats[start:end], desc="Processing journals"): # 31: 1881
                scraper.filter_bookindex_genre(subcat)
                scraper.filter_index_type(subcat)

                # extract texts and metadata
                try:
                    scraper.get_text_metadata(subcat)

                    if processing == "safe":
                        all_text_dicts.update(scraper.text_dict)
                        all_metadata.update(scraper.meta_dict)

                        # Calling here to store information in case of errors that would make it necessary to run everything again.
                        scraper.store_text()
                        scraper.store_metadata()
                        
                        scraper.text_dict = defaultdict(dict)
                        scraper.meta_dict = defaultdict(dict)

                    saved_idx += 1
                except:
                    print(f"\nThe Wiki API raised an error on {scraper.subcats[saved_idx]} (index {saved_idx}). Please run the following command after finishing:\n\tpython3 extract.py -s {saved_idx} -e {saved_idx+1}\n")
        finally:
            if processing == "fast":
                scraper.store_text()
                scraper.store_metadata()
                scraper.store_dicts(scraper.text_dict, scraper.meta_dict)
            else:
                # store text and metadata in files
                scraper.store_dicts(all_text_dicts, all_metadata)
    else:
        # Use the collected texts and metadata for test purposes
        #with open("./test_dicts.json", "r", encoding = "utf-8") as param_file:
            #scraper.text_dict, scraper.meta_dict = json.load(param_file)
        
        #scraper.store_metadata()
        # Programm ausführen
        scraper.get_subcats()
        all_text_dicts = dict()
        all_metadata = dict()
        saved_idx = 0 
        
        try: 
            for subcat in tqdm(scraper.subcats[start:end], desc="Processing journals"): # 31: 1881
                scraper.filter_bookindex_genre(subcat)
                scraper.filter_index_type(subcat)

                # extract texts and metadata
                try:
                    scraper.get_text_metadata(subcat)

                    if processing == "safe":
                        all_text_dicts.update(scraper.text_dict)
                        all_metadata.update(scraper.meta_dict)

                        # Calling here to store information in case of errors that would make it necessary to run everything again.
                        scraper.store_text()
                        scraper.store_metadata()
                        
                        scraper.text_dict = defaultdict(dict)
                        scraper.meta_dict = defaultdict(dict)

                    saved_idx += 1
                except:
                    print(f"\nThe Wiki API raised an error on {scraper.subcats[saved_idx]} (index {saved_idx}). Please run the following command after finishing:\n\tpython3 extract.py -s {saved_idx} -e {saved_idx+1}\n")
        finally:
            if processing == "fast":
                scraper.store_text()
                scraper.store_metadata()
                scraper.store_dicts(scraper.text_dict, scraper.meta_dict)
            else:
                # store text and metadata in files
                scraper.store_dicts(all_text_dicts, all_metadata)







