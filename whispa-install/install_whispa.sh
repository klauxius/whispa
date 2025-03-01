#!/bin/bash

# Install required packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv portaudio19-dev python3-dev

# Create virtual environment
python3 -m venv ~/.whispa-env

# Activate virtual environment and install dependencies
source ~/.whispa/bin/activate
pip install openai sounddevice numpy pynput python-dotenv scipy

# Create the whispa executable
cat > /tmp/whispa << 'EOF'
#!/bin/bash
source ~/.whispa/bin/activate
python3 ~/.local/bin/whispa.py
EOF

# Make it executable and move to system path
sudo mv /tmp/whispa /usr/local/bin/
sudo chmod +x /usr/local/bin/whispa

# Copy the main script to user's bin
mkdir -p ~/.local/bin
cp whispa.py ~/.local/bin/

# Install desktop entry
mkdir -p ~/.local/share/applications
mv whispa.desktop ~/.local/share/applications/whispa.desktop

# Create configuration directory and example .env
mkdir -p ~/.config/whispa
if [ ! -f ~/.config/whispa/.env ]; then
    echo "OPENAI_API_KEY=your_api_key_here" > ~/.config/whispa/.env
fi

echo "Installation complete! Please edit ~/.config/whispa/.env and add your OpenAI API key." 