# gtk-dock-x11


A lightweight and modern desktop dock for Linux (X11).
It is built using a combination of GTK3 and Xlib, and is specifically designed to run smoothly with window managers such as Openbox.


## Features


- **Modern Design**: A stylish appearance featuring rounded corners, transparent backgrounds, and hover animations.
- **Window List**: Displays running applications in real time and allows you to activate a window by clicking it.
- **App Launcher**: Can launch `lightpad` from the left button.
- **Status Display**: Compactly displays network, volume, and clock information.
- **Openbox Optimization**: Bypasses automatic placement rules and controls coordinates at the Xlib level to ensure windows are securely pinned to the bottom of the screen.


## Prerequisites


The following packages are required for operation (example for Ubuntu/Debian-based systems):


```bash
sudo apt install python3-gi python3-xlib gir1.2-gtk-3.0
```


Additionally, we recommend using **Papirus** as the icon theme.


## How to Use


Simply clone the repository and run it in Python.


```bash
python3 dock_app.py
```

## Settings


Currently, the following settings are configured using variables within the code:


* **APP_ID**: none
* **Launcher**: Configured to call `io.github.libredeb.lightpad`.
* **Appearance**: You can freely change colors and opacity by modifying the CSS within the `load_css()` method.


## License
GNU GPL 3.0
