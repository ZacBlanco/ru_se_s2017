python3 -c 'import os, subprocess; os.environ["FLASK_APP"]="chefboyrd/__init__.py"; os.environ["FLASK_DEBUG"]="1"; subprocess.Popen(["flask run --host=0.0.0.0"], shell=True).wait()'
