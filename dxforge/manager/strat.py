from typing import Union

import dxlib
from dxlib import History


class MyStrat(dxlib.Strategy):
    def output_schema(self, history: Union[History, None]):
        pass

    def execute(self, observation: History, history: History, history_view, *args, **kwargs) -> History:
        pass
