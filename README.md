

# Preparation
Is recommended to create a python environment to install packages without conflicts

'''python3 -m venv /path/to/project/src'''
'''source ./bin/activate'''
'''pip install -r requirements.txt'''

# Usage (don't forget to change the scritps permission with chmod +x ./redact_all.sh)
'''
./redact_all.sh ./path/to/input ./path/to/output
'''

Input should be a dir which contains at least one team dir. a team dir is a dir with pdfs that neet to be redacted.

/input/
    /team1/
        cv1.pdf
        cv2.pdf
    /team2/
        cv1.pdf
