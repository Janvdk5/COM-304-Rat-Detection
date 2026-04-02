import serial.tools.list_ports
import re
import os

import ctypes
import string 

def find_com_port(keyword="Application"):
    """Automatically find a COM port matching a keyword in its description."""
    for p in serial.tools.list_ports.comports():
        if keyword.lower() in p.description.lower():
            # Extract the COM number, e.g. "COM7" -> 7
            match = re.search(r"COM(\d+)", p.device, re.IGNORECASE)
            if match:
                return int(match.group(1))
    raise RuntimeError("No matching COM port found")

def update_com_port_in_file(filename, new_port_num):
    """Replace COM_PORT = X line regardless of extra spaces."""
    pattern = r"^\s*COM_PORT\s*=\s*\d+\s*$"
    replacement = f"COM_PORT = {new_port_num}"

    with open(filename, "r") as f:
        content = f.read()

    # Replace only the COM_PORT line that matches the pattern
    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    with open(filename, "w") as f:
        f.write(new_content)
    print('sucess')

def find_rtt_dll(start_dirs=None, filename="RtttNetClientAPI.dll"):
    """
    Recursively search for RtttNetClientAPI.dll starting from the given directories.
    """
    if start_dirs is None:
        start_dirs = [
            r"C:\ti",
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            r"D:\ti",
            r"D:\Program Files",
            r"D:\Program Files (x86)",
        ]
    
    for root_dir in start_dirs:
        for root, dirs, files in os.walk(root_dir):
            if filename in files:
                return os.path.join(root, filename)
    return None


def update_rtt_path_in_file(file_path, dll_path):
    """
    Replace ANY line containing *.rtt_path = r'...'
    Handles:
        rtt_path = ...
        self.rtt_path = ...
        obj.rtt_path = ...
    """
    # Regex:
    #   ^\s*                 -> optional leading spaces
    #   [\w\.]*              -> optional prefix like self., obj., myclass.module.
    #   rtt_path             -> the variable name
    #   \s*=\s*              -> equal with any spaces
    #   r?['"](.*?)['"]      -> capture quoted path, optional raw prefix
    pattern = r"^\s*[\w\.]*rtt_path\s*=\s*r?['\"](.*?)['\"]"

    with open(file_path, "r") as f:
        content = f.read()

    # Use a lambda to avoid path escape interpretation
    new_content = re.sub(
        pattern,
        lambda m: f"        self.rtt_path = r'{dll_path}'",
        content,
        flags=re.MULTILINE
    )

    with open(file_path, "w") as f:
        f.write(new_content)

    print(f"Updated rtt_path -> {dll_path}")
    return True


def list_files(path):
    """Return a list of full paths for all files inside a directory (non-recursive)."""
    return [
        os.path.join(path, f)
        for f in os.listdir(path)
        if os.path.isfile(os.path.join(path, f))
    ]


# -----------------------------
# # Example usage
# # -----------------------------
# if __name__ == "__main__":
#     print("Searching for RtttNetClientAPI.dll...")

#     dll_path = find_rtt_dll()  # searches C:\ti and Program Files by default

#     if dll_path:
#         print("Found DLL at:", dll_path)
#         update_rtt_path_in_file("task1_capture.py", dll_path)
#     else:
#         print("Could not find RtttNetClientAPI.dll on this machine.")


# if __name__ == "__main__":
#     com_number = find_com_port("Application")  # or "Arduino", etc.
#     print("Detected COM port number:", com_number)

#     update_com_port_in_file("scripts/1843_config.lua", com_number)
#     print("Updated scripts/1843_config.lua with COM_PORT =", com_number)
