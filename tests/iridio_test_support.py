import importlib
from pathlib import Path
import sys
import types

package = types.ModuleType('iridio_under_test')
package.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules.setdefault(package.__name__, package)


def module(name):
    return importlib.import_module(f'{package.__name__}.{name}')
