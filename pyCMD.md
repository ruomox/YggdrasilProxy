## Requirements:
```bash
conda create -n YggdrasilProxy python=3.11 -y
conda activate YggdrasilProxy
pip install -r requirements.txt
```

## Windows:
```bash
pyinstaller -F --collect-all cryptography --add-data "assets\fMcMain.jar;assets" --add-data "assets\authlib-injector.jar;assets" --add-data "assets\javaw.exe;assets" --add-data "assets\javac.exe;assets" --add-data "assets\YggProJAVA.zip;assets" --name "YggdrasilProxy" run.py
```

## MacOS:
```bash
pyinstaller -F --collect-all cryptography --add-data "assets/YggProJAVA.zip:assets" --add-data "assets/fMcMain.jar:assets" --add-data "assets/authlib-injector.jar:assets" --name="YggdrasilProxy" run.py
```