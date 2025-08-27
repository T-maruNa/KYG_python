from .sumi import Sumirei
from .sakurada import SakuradaMirai

def get_analysts():
    """
    アナリストのインスタンスを取得する

    Returns:
        List[object]: アナリストのインスタンスのリスト
    """
    return [Sumirei(), SakuradaMirai()] 
