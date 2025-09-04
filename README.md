# TIMage (pPainter)

A simple PSX TIM image editor/viewer built with PyQt6. Supports editing, palette manipulation, and exporting to common image formats.

## How To

- Run [GTVolTools] : (https://github.com/adeyblue/GTVolTools/releases/tag/v1) 

- Extract [VOL] as instructed

- Once your VOL is extracted open [pPainter] 

- Load the [TIM] file you wish to edit which is located in the [carwheel] folder. 


## Features

- Open and edit PSX TIM files (4/8/16/24 bpp)
- Palette editing for indexed images
- Export to PNG, 
- Save as TIM or standard image formats 

## Requirements

- Python 3.8+
- [PyQt6](https://pypi.org/project/PyQt6/)
- [Pillow](https://pypi.org/project/Pillow/)
- [PyInstaller](https://pypi.org/project/pyinstaller/) 
Install dependencies:

```sh
pip install -r requirements.txt
```

## Running

To run the program:

```sh
python ppainter.py
```

## Building the Executable (.exe)

1. Install PyInstaller if not already installed:

    ```sh
    pip install pyinstaller
    ```

2. Build the executable:

    ```sh
    pyinstaller --onefile --windowed --icon=ico.ico ppainter.py
    ```

   - The output `.exe` will be in the `dist/` directory.

3. (Optional) To include the icon and other resources, make sure they are in the same directory as the `.exe` or specify them in the PyInstaller spec file.

## Files

- `ppainter.py` - Main application source
- `requirements.txt` - Python dependencies
- `ico.ico`, `ico.png` - Application icons
- `ppainter.spec` - PyInstaller build specification (optional)
- `build/` - Build output directory

## License

MIT License (or specify your license here)