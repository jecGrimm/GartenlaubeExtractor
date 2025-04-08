#!/bin/bash
#
#SBATCH --job-name=gartenlaube_extractor
#SBATCH --comment="Extract text and metadata from of the Gartenlaube from wikisource"
#SBATCH --mail-type=ALL
#SBATCH --mail-user=j.grimm@campus.lmu.de
#SBATCH --chdir=/home/c/janagrimm@141.84.137.23/Desktop/GartenlaubeExtractor
#SBATCH --output=/home/c/janagrimm@141.84.137.23/Desktop/GartenlaubeExtractor/slurm.%j.%N.out]
#SBATCH --ntasks=1

python3 -u extract.py