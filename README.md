![App Icon](ico.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

# TIMage (pPainter)

A simple PSX TIM image editor/viewer built with PyQt6. Supports editing, palette manipulation, and exporting to common image formats.


## How To Use

- Run [GTVolTools](https://github.com/adeyblue/GTVolTools/releases/tag/v1) 

- Extract [VOL] as instructed

- Once your VOL is extracted open [pPainter](https://github.com/JeevesGB/pPainter-v2/releases/tag/ppaint-v1.0.2)

- Load the TIM file you wish to edit which is located in the [carwheel] folder. 

- Save file 

- In [GTVolTools](https://github.com/adeyblue/GTVolTools/releases/tag/v1) select "Make GT2 VOL from Directory" 

- Once process is finished replace the VOL from and original copy of Gran Turismo 2 NTSC using [UltraISO](https://www.ultraiso.com/download.html)

- Save As (Give it your own name) 

- Run the new .BIN file in duckstation. 


## Features

- Open and edit PSX TIM files (4/8/16/24 bpp)
- Palette editing for indexed images
- Export to PNG, 
- Save as TIM or standard image formats 

## Credits

- [GTModding-Hub](https://nenkai.github.io/gt-modding-hub/ps1/gt2/tools/#tools)
- [Adeyblue](https://github.com/adeyblue)
- [Pez2k](https://github.com/pez2k)
- [GTModding-Discord](https://discord.com/invite/YbJjbYEKzB)

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

