pip install -U pip
pip install -U setuptools
conda install -y numpy pandas
CPATH=/usr/local/include LIBRARY_PATH=/usr/local/lib pip install pyaudio
pip install -r requirements.txt

echo ""
echo "Fetching videos from rhino..."
echo ""
./getvideos.sh
