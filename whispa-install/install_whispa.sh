#!/bin/bash

# Installation paths
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="$HOME/.config/whispa"
APP_DIR="$HOME/.local/share/applications"
VENV_DIR="$CONFIG_DIR/venv"

# Check if script is in the correct directory
if [ ! -f "whispa.py" ]; then
    echo "Error: whispa.py not found in current directory"
    echo "Please run this script from the directory containing whispa.py"
    exit 1
fi

# Cleanup function
cleanup_old_installation() {
    echo "Cleaning up old installation..."
    
    # Remove old executable
    sudo rm -f "$INSTALL_DIR/whispa"
    rm -f "$HOME/.local/bin/whispa"
    
    # Remove old desktop entry
    rm -f "$APP_DIR/whispa.desktop"
    
    # Backup existing config files
    if [ -f "$CONFIG_DIR/.env" ]; then
        cp "$CONFIG_DIR/.env" "$CONFIG_DIR/.env.backup"
        echo "Backed up existing .env file to .env.backup"
    fi
    
    # Backup existing settings
    if [ -f "$CONFIG_DIR/settings.json" ]; then
        cp "$CONFIG_DIR/settings.json" "$CONFIG_DIR/settings.json.backup"
        echo "Backed up existing settings.json file to settings.json.backup"
    fi
    
    # Remove old virtual environment and script filet
    rm -rf "$VENV_DIR"
    rm -f "$CONFIG_DIR/whispa.py"
    
    echo "Cleanup complete"
}

# Run cleanup before installation
cleanup_old_installation

# Create necessary directories
mkdir -p "$CONFIG_DIR"
mkdir -p "$APP_DIR"

# Install required packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv portaudio19-dev python3-dev

# Create and activate virtual environment
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate" || {
    echo "Error: Failed to activate virtual environment"
    exit 1
}

# Install Python dependencies
pip install --no-warn-script-location openai sounddevice numpy python-dotenv scipy
pip install --no-warn-script-location pynput==1.7.6  # Use a specific version of pynput

# Install the Whispa application
echo "Installing Whispa..."

# Create the executable script
cat > /tmp/whispa << EOF
#!/bin/bash

# Ensure X11 display access for GUI and keyboard listener
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

# Ensure we have a valid Xauthority file
if [ ! -f "$XAUTHORITY" ] && [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

# Activate virtual environment and run program
source "$VENV_DIR/bin/activate"
exec python3 "$CONFIG_DIR/whispa.py"
EOF

# Make it executable and move to system path
sudo mv /tmp/whispa "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/whispa"

# Copy the main script to config directory
cp whispa.py "$CONFIG_DIR/" || {
    echo "Error: Failed to copy whispa.py"
    exit 1
}

# Create desktop entry
cat > "$APP_DIR/whispa.desktop" << EOF
[Desktop Entry]
Version=1.0
Name=Whispa
GenericName=Voice to Text
Comment=Multilingual voice-to-text transcription (Insert key to record)
Exec=$INSTALL_DIR/whispa
Icon=audio-input-microphone
Terminal=false
Type=Application
Categories=Utility;AudioVideo;Accessibility;
Keywords=voice;recording;transcription;whisper;speech;multilingual;
StartupNotify=true
X-GNOME-Autostart-enabled=true
EOF

# Create default config if it doesn't exist
if [ ! -f "$CONFIG_DIR/.env" ]; then
    echo "OPENAI_API_KEY=your_api_key_here" > "$CONFIG_DIR/.env"
fi

# Restore settings if backup exists
if [ -f "$CONFIG_DIR/settings.json.backup" ]; then
    cp "$CONFIG_DIR/settings.json.backup" "$CONFIG_DIR/settings.json"
    echo "Restored settings from backup"
fi

# Restore .env if backup exists
if [ -f "$CONFIG_DIR/.env.backup" ] && [ ! -f "$CONFIG_DIR/.env" ]; then
    cp "$CONFIG_DIR/.env.backup" "$CONFIG_DIR/.env"
    echo "Restored .env from backup"
fi

echo "Installation complete!"
echo "Please:"
echo "1. Edit $CONFIG_DIR/.env and add your OpenAI API key (if not already done)"
echo "2. Log out and log back in for the changes to take effect"
echo "3. Set up the Super+F9 keyboard shortcut in Settings to run 'whispa'"

# Verify installation
if [ -x "$INSTALL_DIR/whispa" ] && [ -f "$CONFIG_DIR/whispa.py" ] && [ -f "$APP_DIR/whispa.desktop" ]; then
    echo "Verification: All files installed correctly"
else
    echo "Warning: Some files may not have installed correctly"
    echo "Please check the error messages above"
fi 