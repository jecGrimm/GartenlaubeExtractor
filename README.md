# Gartenlaube Extractor
This script extracts the Gartenlaube articles from wikisource, splits them up into episodes and stores the episodes and whole texts in plain-txt files. The whole script is build to add new serial publications to the corpus on serial literature in the 19th century by [Prof. Dr. Julian Schröter at the LMU Munich](https://www.germanistik.uni-muenchen.de/personal/ndl/professoren/schroeter/index.html).

The module deploys the following pipeline for the extraction:
![Pipeline Gartenlaube Extractor](./visualizations/pipeline_GartenlaubeExtractor.pdf)
![Pipeline with questions](./visualizations/pipeline_questions.pdf)

## Installation
Clone and add submodules:<br> 
`git clone --recurse-submodules git@github.com:jecGrimm/GartenlaubeExtractor.git`

If the repository has already been cloned without initializing the submodules, please run <br>
`git submodule update --init --recursive` <br>
to add the submodules afterwards. Without this command, the directory `resources/nschatz_deu` is empty.

## Usage
### CLI
`python3 extract.py`

The optional argument `-m (test|run)` specifies whether the texts and metadata should be extracted from wikisource from scratch (modus `run`). If the modus `test` is activated, the already extracted texts and metadata are drawn from the file `test_dicts.json` (if available). In this case, please specify which functions should be tested.

### Environment
The packages needed to run the script are stored in the file `gartenlaube_environment.yml`. To create your own environment for this script, follow these steps:

1. Install [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).
2. Run `conda env create -f gartenlaube_environment.yml` in your terminal to create the `gartenlaube` environment used to run this script.
3. Run `conda activate gartenlaube` to activate the environment before running the script.

## Structure
### extract.py
Script with the class GartenlaubeExtractor containing all of the needed methods to extract texts and save them.

### test_dicts.json
List containing the last extracted text_dicts and meta_dicts. This file can be used for testing purposes.

### output
The output is stored in the `output`-directory. This directory contains to sub-directories `episodes` and `whole_texts`.<br> 

#### texts
`episodes` contains the split up text files for serial publications. The filename has the following structure:<br> <document_raw_id>-<episode_id>\_\<title>\_\<year>\_\<journal><br> 

`whole_texts` contains the whole text files for all publications regardeless of their seriality. The filename has the following structure:<br> <document_raw_id>-00\_\<title>\_\<year>\_\<journal><br>

#### metadata
The metadata is appended at the end of to the existing file `Bibliographie.csv`.

### resources
#### black_list
Directory containing csv-files that list text titles that should not be extracted from wikidata.

#### names
Directory containing json-files with lists of popular german names to split the author names into first names and last names.

#### nschatz_deu
Directory containing the xml-files for the texts in the corpus Deutscher Novellenschatz. The titles of these publications are used to mark them in "Bibliographie.csv".

## Coding decisions
### Text
#### Splitting episodes
A whole text is split episodes every time the page number is not continous.

Epsiode text files are created only when a text consists of more than one episode.

#### Splitting paragraphs
The paragraphs are split by newline and reproduce therefore the paragraph structure of wikisource. 

The paragraphs are extracted by the `get_text()`-method provided by BeautifulSoup. If there are two html text components without a newline separating them, `get_text()` combines them in one line. These cases are therefore also concatenated in the created output file, while they may appear differently in wikisource.

For each page, a new paragraph is created. This is not the case in wikisource. Pages are marked with their number in the format `[<number>]`.

#### Images
Images are replaced by an empty line.

Image captions are removed from the text.

#### Emphasized words
Words and characters that are emphasized on wikisource are not emphasized in the output text.  

### Metadata
#### Splitting author names 
The author names are split into first names and last names by checking their occurence in the `names` directory retrieved from [github](https://github.com/Jonas0204/Oilrig/tree/master/json).

If the name does not exist in one of the lists of names, the last name-part is saved as lastname and the rest as firstnames.

#### Gender
The gender is assumed by checking in which list of firstnames (male or female) the first name appears. Please note that we only include binary gender labels and that our assumptions might be incorrect. The assumptions are used to approximate the percentage of possibly female authors compared to possibly male authors.  

#### Position in the journal
The field `Nummer im Heft (ab 00797: 1 erste Position. 0 nicht erste Position)` is true if the text occurs at the first position of the journal. However, this script only returns true if the text is printed on the first page of the journal.

#### Pages
The field `Seiten` marks the pages of the text in the journal. Unfortunately, wikisource does not always provide the page numbers for each episode. In these cases, the field is filled with the page numbers for the whole article. 

## Limitations
### Text
#### Quality
As the texts are automatically collected from wikisource, we cannot account for their quality and correctness. However, wikisource provides the scans of the original work on [Commons](https://commons.wikimedia.org/wiki/). Therefore, the quality can be inspected manually when in doubt.

#### Bias
The Gartenlaube is a journal containing texts from the 19th century. Many of these texts might contain bias and discriminative ideas. Please be aware of that and read these texts with a critical mind. 

### Metadata
The following fields are not automatically filled in the metadata table:
- `Pseudonym`
- `Untertitel im Text`
- `Untertitel im Inhaltsverzeichnis`
- `Gattungslabel_ED`
- `Gattungslabel_ED_normalisiert`
- `Medium_Zweitdruck`
- `Jahr_Zweitdruck`
- `Label_Zweitdruck`
- `Medium_Drittdruck`
- `Jahr_Drittdruck`
- `Label_Drittdruck`
- `in_Pantheon`
- `in_RUB_Sammlung`
- `in_B-v-Wiese`
- `Verantwortlich_Erfassung`
- `falls_andere_Quelle`
- `Herkunft_Prätext_lt_Paratext`
- `Wahrheitsbeglaubigung_lt_Paratext`
- `ist_spätere_Fassung_von`

### Future Work
- Extract missing fields in the metadata. 
- Make position in the journal, author name, and gender detection more robust.
- Collect more novellas via the category "Novelle" in wikisource.
- Collect more texts of the authors.
- Filter the texts accurately for novellas.
