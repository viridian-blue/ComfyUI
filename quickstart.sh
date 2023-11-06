

# get submodules
git submodule update --init --recursive

# install dependencies
pip install -r requirements.txt

# launch
python3 main.py --listen 0.0.0.0 $@