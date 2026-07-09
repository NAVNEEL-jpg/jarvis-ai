import os
import sys
from dotenv import load_dotenv

# Path setup
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

from mcp.server.fastmcp import FastMCP
from smart_home import JarvisSmartHome

# Create FastMCP server instance
mcp = FastMCP("JarvisSmartHome")

# Initialize smart home driver lazily when tools are first called
_home = None

def get_home():
    global _home
    if _home is None:
        _home = JarvisSmartHome()
    return _home

@mcp.tool()
def list_smart_devices() -> str:
    """
    List all smart home devices across Amazon Alexa, Google Home/Nest, and Home Assistant integrations.
    """
    home = get_home()
    devices = []
    
    # 1. Alexa devices
    if home.alexa.available and home.alexa._ready:
        try:
            devices.extend([f"{d} (Alexa)" for d in home.alexa.list_smart_home()])
        except Exception:
            pass
        
    # 2. Google Home devices
    if home.google.available and home.google._ready:
        try:
            devices.extend([f"{gd} (Google Home)" for gd in home.google.list_devices()])
        except Exception:
            pass
        
    # 3. Home Assistant
    if home.ha.available:
        try:
            entities = home.ha.list_entities("light") + home.ha.list_entities("switch")
            devices.extend([f"{e.split('.')[-1].replace('_', ' ')} (Home Assistant)" for e in entities])
        except Exception:
            pass
        
    if not devices:
        return "No smart home devices discovered. Make sure credentials are set in the Web Control Panel."
        
    return "Discovered Smart Devices:\n" + "\n".join(f"- {d}" for d in sorted(set(devices)))

@mcp.tool()
def turn_on_device(device: str, room: str = None) -> str:
    """
    Turn on a smart home light, fan, switch, plug, or AC.
    
    Args:
        device: The name of the device (e.g. "living room light", "bedroom fan").
        room: Optional room context.
    """
    home = get_home()
    return home.turn_on(device, room)

@mcp.tool()
def turn_off_device(device: str, room: str = None) -> str:
    """
    Turn off a smart home light, fan, switch, plug, or AC.
    
    Args:
        device: The name of the device (e.g. "kitchen plug", "all lights").
        room: Optional room context.
    """
    home = get_home()
    return home.turn_off(device, room)

@mcp.tool()
def speak_announcement(message: str, speaker_device: str = "all") -> str:
    """
    Announce / broadcast a voice message on Google Nest, Nest Hub, or Chromecast speakers.
    
    Args:
        message: The text to announce (e.g. "Dinner is ready", "Someone is at the door").
        speaker_device: The name of the specific speaker to target, or "all" to broadcast to every speaker.
    """
    home = get_home()
    return home.announce(message, speaker_device)

if __name__ == "__main__":
    mcp.run()
