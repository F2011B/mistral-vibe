import vibe
import os
import sys

print(f"Python Executable: {sys.executable}")
print(f"Vibe Package Location: {os.path.dirname(vibe.__file__)}")
print(f"Current Working Directory: {os.getcwd()}")
