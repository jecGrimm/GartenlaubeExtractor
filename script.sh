#!/bin/bash
#
#SBATCH --job-name=gartenlaube_extractor
#SBATCH --comment="Extract text and metadata from of the Gartenlaube from wikisource"
#SBATCH --mail-type=ALL
#SBATCH --mail-user=j.grimm@campus.lmu.de
#SBATCH --chdir=/home/j/janagrimm@141.84.137.23/GartenlaubeExtractor
#SBATCH --output=/home/j/janagrimm@141.84.137.23/GartenlaubeExtractor/slurm.%j.%N.out
#SBATCH --ntasks=1

python3 -u extract.py