import logging
from pathlib import Path
import signal
import subprocess
import sys
import threading
import yaml

# TODO 停止命令を受けたときの処理
# TODO Yamlの設定ファイルを読み込みそれを使うように修正
# TODO 一時停止コマンド系の追加

SLEEP_TIME: int = 60 * 5
PING_COOLTIME: int = 30
CONFIG_PATH = Path("/etc/server-guardian/config.yml")

# systemdに流すためのシンプルなフォーマット設定
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s' # 日時(asctime)やプロセスIDはsystemdが自動付与するため不要
)


shutdown_event = threading.Event()

class ServerGuardian:
    
    def __init__(self, mac: str, ip: str, name: str):
        self.__mac = mac
        self.__ip = ip
        self.__name = name
        self.__alive: bool | None = None
        self.__wol_count: int = 0
    
    def ping(self) -> bool:
        command = ["ping", "-c", "1", "-W", "2", self.__ip]
        res = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    
    def send_wol(self) -> None:
        command = ["wakeonlan", self.__mac]
        res = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            logging.error(res.stderr)
    
    def main(self) -> None:
        try:
            while not shutdown_event.is_set():
                try:
                    for i in range(3):
                        if self.ping():
                            if self.__alive is False:
                                logging.info(
                                    f"[{self.__name}] が復帰しました。起動までのWOL試行回数: {self.__wol_count}回"
                                )
                                self.__alive = True
                                self.__wol_count = 0
                            elif self.__alive is None:
                                self.__alive = True
                            
                            break
                        if shutdown_event.wait(timeout=PING_COOLTIME):
                            break
                    else:
                        self.__alive = False
                        self.__wol_count += 1
                        logging.warning(
                            f"[{self.__name}] の応答がありません。WOLを送信します（試行 {self.__wol_count}回目）"
                        )
                        self.send_wol()
                except Exception as e:
                    logging.error(f"[{self.__name}] 監視中にエラーが発生しました: {e}")
                    
                shutdown_event.wait(timeout=SLEEP_TIME)
        except Exception as e:
            # 万が一スレッド内で未知のエラーが起きてもシステムを安全にログに残す
            logging.error(f"[{self.__name}] 監視中にエラーが発生しました: {e}")
        finally:
            # 正常終了時も例外発生時も必ず通るクリーンアップ処理
            logging.info(f"[{self.__name}] 監視スレッドを終了しました。")

def handle_shutdown(signum, frame):
    """systemd(SIGTERM) や Ctrl+C(SIGINT) を受け取るハンドラ"""
    logging.info("停止命令を受信しました。クリーンアップを開始します...")
    shutdown_event.set()  # すべての wait() を一瞬で解除して終了へ向かわせる

def load_config() -> dict:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            raise ValueError("設定ファイルが空です。")

        if "targets" not in config:
            raise ValueError("'targets' がありません。")

        if not isinstance(config["targets"], list):
            raise ValueError("'targets' はリストである必要があります。")

        for target in config["targets"]:
            for key in ("name", "ip", "mac"):
                if key not in target:
                    raise ValueError(f"'{key}' がありません。")

        return config

    except FileNotFoundError:
        logging.critical(f"設定ファイルが見つかりません: {CONFIG_PATH}")
        sys.exit(1)

    except yaml.YAMLError as e:
        logging.critical(f"YAMLの解析に失敗しました: {e}")
        sys.exit(1)

    except ValueError as e:
        logging.critical(f"設定ファイルが不正です: {e}")
        sys.exit(1)

    except Exception as e:
        logging.critical(f"設定ファイルの読み込み中に予期しないエラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    config = load_config()

    targets = config["targets"]
    
    
    threads: list[threading.Thread] = []
    
    logging.info("WOL監視サービスを起動します。")
    logging.info(
        f"監視対象: {len(targets)} 台"
    )
    
    for target in targets:
        monitor_instance = ServerGuardian(
            mac=target["mac"], 
            ip=target["ip"], 
            name=target["name"]
        )
        
        t = threading.Thread(target=monitor_instance.main, daemon=True)
        t.start()
        threads.append(t)

    try:
        # メインスレッドは停止シグナルがセットされるまで1秒ごとに待機
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        # Ctrl+Cを直接叩かれた場合の保険
        shutdown_event.set()
    
    for t in threads:
        t.join()
    
    logging.info("すべての処理が完了しました。サービスを停止します。")