#!/usr/bin/env python3
"""
MP3音声ファイル分割ツール - GUI版
洗練されたインターフェースで音声ファイルを時間ごとに分割
"""

import os
import sys
import threading
import logging
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from pydub import AudioSegment
import queue
import time
import subprocess
import shutil
import locale
from dotenv import load_dotenv, set_key

# システムのデフォルトエンコーディングを取得
SYSTEM_ENCODING = locale.getpreferredencoding()

# ロギングの設定
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'audio-splitter.log')
env_file = os.path.join(script_dir, '.env')

# 既存のログファイルを削除
if os.path.exists(log_file):
    try:
        os.remove(log_file)
        print(f"既存のログファイルを削除しました: {log_file}")
    except Exception as e:
        print(f"ログファイルの削除に失敗しました: {str(e)}")

# ロギングの設定
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    filemode='w'  # 新規作成モード
)

logging.info(f"ログファイルを作成しました: {log_file}")

def load_settings():
    """設定を.envファイルから読み込む"""
    if os.path.exists(env_file):
        load_dotenv(env_file)
        return {
            'input_file': os.getenv('INPUT_FILE', ''),
            'output_dir': os.getenv('OUTPUT_DIR', ''),
            'split_duration': int(os.getenv('SPLIT_DURATION', '90')),
            'preserve_quality': os.getenv('PRESERVE_QUALITY', 'True').lower() == 'true',
            'auto_open_folder': os.getenv('AUTO_OPEN_FOLDER', 'True').lower() == 'true'
        }
    return {
        'input_file': '',
        'output_dir': '',
        'split_duration': 90,
        'preserve_quality': True,
        'auto_open_folder': True
    }

def save_settings(settings):
    """設定を.envファイルに保存"""
    try:
        # .envファイルが存在しない場合は作成
        if not os.path.exists(env_file):
            with open(env_file, 'w', encoding='utf-8') as f:
                pass
        
        # 設定を保存
        set_key(env_file, 'INPUT_FILE', settings['input_file'])
        set_key(env_file, 'OUTPUT_DIR', settings['output_dir'])
        set_key(env_file, 'SPLIT_DURATION', str(settings['split_duration']))
        set_key(env_file, 'PRESERVE_QUALITY', str(settings['preserve_quality']))
        set_key(env_file, 'AUTO_OPEN_FOLDER', str(settings['auto_open_folder']))
        
        logging.info("設定を.envファイルに保存しました")
    except Exception as e:
        logging.error(f"設定の保存に失敗: {str(e)}")

def check_ffmpeg():
    """FFmpegが利用可能かチェック"""
    try:
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            logging.error("FFmpegが見つかりません")
            return False
        
        result = subprocess.run([ffmpeg_path, '-version'], 
                              capture_output=True, 
                              encoding=SYSTEM_ENCODING,
                              errors='replace',
                              check=True)
        logging.info(f"FFmpegバージョン: {result.stdout.split('\\n')[0]}")
        return True
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logging.error(f"FFmpegの確認に失敗: {str(e)}")
        return False

class AudioSplitterGUI:
    def __init__(self, root):
        logging.info("アプリケーションを起動")
        self.root = root
        self.setup_window()
        self.setup_variables()
        self.setup_ui()
        self.progress_queue = queue.Queue()
        self.check_progress()
        
        # FFmpegの確認
        if not check_ffmpeg():
            messagebox.showerror("エラー", "FFmpegがインストールされていないか、パスが通っていません。\nFFmpegをインストールしてから再起動してください。")
            self.root.destroy()
            return
    
    def setup_window(self):
        """ウィンドウの基本設定"""
        self.root.title("Audio Splitter")
        self.root.geometry("600x700")  # 縦幅を480から700に変更
        self.root.minsize(600, 700)    # 最小サイズも設定
        self.root.resizable(True, True)
        
        # アイコンとスタイル設定
        style = ttk.Style()
        style.theme_use('clam')
        
        # カスタムスタイル
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 11, 'bold'))
        style.configure('Info.TLabel', font=('Helvetica', 9))
        style.configure('Success.TLabel', foreground='green', font=('Helvetica', 9, 'bold'))
        style.configure('Error.TLabel', foreground='red', font=('Helvetica', 9, 'bold'))
        
        # 進捗バーのスタイル設定
        style.configure("Green.Horizontal.TProgressbar", 
                       troughcolor='#E0E0E0',
                       background='#4CAF50',  # グリーン
                       thickness=20)
    
    def setup_variables(self):
        """変数の初期化"""
        # 設定を読み込む
        settings = load_settings()
        
        self.input_file = StringVar(value=settings['input_file'])
        self.output_dir = StringVar(value=settings['output_dir'])
        self.split_duration = IntVar(value=settings['split_duration'])
        self.preserve_quality = BooleanVar(value=settings['preserve_quality'])
        self.auto_open_folder = BooleanVar(value=settings['auto_open_folder'])
        self.current_operation = None
    
    def setup_ui(self):
        """UIコンポーネントの作成"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(W, E, N, S))
        
        # グリッド設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # タイトル
        title_label = ttk.Label(main_frame, text="🎵 Audio Splitter", style='Title.TLabel')
        title_label.grid(row=row, column=0, columnspan=3, pady=(0, 20))
        row += 1
        
        # 入力ファイル選択
        ttk.Label(main_frame, text="入力ファイル:", style='Header.TLabel').grid(row=row, column=0, sticky=W, pady=(0, 5))
        row += 1
        
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=row, column=0, columnspan=3, sticky=(W, E), pady=(0, 15))
        input_frame.columnconfigure(0, weight=1)
        
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_file, font=('Helvetica', 9))
        self.input_entry.grid(row=0, column=0, sticky=(W, E), padx=(0, 10))
        
        ttk.Button(input_frame, text="📁 選択", command=self.select_input_file).grid(row=0, column=1)
        row += 1
        
        # 出力フォルダ選択
        ttk.Label(main_frame, text="出力フォルダ:", style='Header.TLabel').grid(row=row, column=0, sticky=W, pady=(0, 5))
        row += 1
        
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=row, column=0, columnspan=3, sticky=(W, E), pady=(0, 15))
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_dir, font=('Helvetica', 9))
        self.output_entry.grid(row=0, column=0, sticky=(W, E), padx=(0, 10))
        
        ttk.Button(output_frame, text="📁 選択", command=self.select_output_dir).grid(row=0, column=1)
        row += 1
        
        # 設定セクション
        settings_frame = ttk.LabelFrame(main_frame, text="分割設定", padding="15")
        settings_frame.grid(row=row, column=0, columnspan=3, sticky=(W, E), pady=(0, 15))
        settings_frame.columnconfigure(1, weight=1)
        row += 1
        
        # 分割時間設定
        ttk.Label(settings_frame, text="分割時間:").grid(row=0, column=0, sticky=W, pady=5)
        
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.grid(row=0, column=1, sticky=(W, E), pady=5, padx=(10, 0))
        
        duration_spinbox = ttk.Spinbox(duration_frame, from_=1, to=300, width=8, textvariable=self.split_duration)
        duration_spinbox.grid(row=0, column=0, sticky=W)
        
        ttk.Label(duration_frame, text="分", style='Info.TLabel').grid(row=0, column=1, sticky=W, padx=(5, 0))
        
        # プリセットボタン
        preset_frame = ttk.Frame(duration_frame)
        preset_frame.grid(row=0, column=2, sticky=W, padx=(20, 0))
        
        ttk.Button(preset_frame, text="30分", width=6, command=lambda: self.split_duration.set(30)).grid(row=0, column=0, padx=2)
        ttk.Button(preset_frame, text="60分", width=6, command=lambda: self.split_duration.set(60)).grid(row=0, column=1, padx=2)
        ttk.Button(preset_frame, text="90分", width=6, command=lambda: self.split_duration.set(90)).grid(row=0, column=2, padx=2)
        
        # オプション設定
        options_frame = ttk.Frame(settings_frame)
        options_frame.grid(row=1, column=0, columnspan=2, sticky=(W, E), pady=(10, 0))
        
        ttk.Checkbutton(options_frame, text="高品質を保持 (処理時間が長くなります)", 
                       variable=self.preserve_quality).grid(row=0, column=0, sticky=W)
        
        ttk.Checkbutton(options_frame, text="完了後に出力フォルダを開く", 
                       variable=self.auto_open_folder).grid(row=1, column=0, sticky=W, pady=(5, 0))
        
        # ファイル情報表示
        self.info_frame = ttk.LabelFrame(main_frame, text="ファイル情報", padding="15")
        self.info_frame.grid(row=row, column=0, columnspan=3, sticky=(W, E), pady=(0, 15))
        
        self.info_label = ttk.Label(self.info_frame, text="ファイルを選択してください", style='Info.TLabel')
        self.info_label.grid(row=0, column=0, sticky=W)
        row += 1
        
        # 進捗バー
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.grid(row=row, column=0, columnspan=3, sticky=(W, E), pady=(0, 15))
        self.progress_frame.columnconfigure(0, weight=1)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, 
                                          mode='determinate',
                                          style="Green.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky=(W, E), pady=(0, 5))
        
        self.progress_label = ttk.Label(self.progress_frame, text="", style='Info.TLabel')
        self.progress_label.grid(row=1, column=0, sticky=W)
        row += 1
        
        # 実行ボタン
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=(10, 0))
        
        self.start_button = ttk.Button(button_frame, text="🚀 分割開始", command=self.start_splitting, 
                                      style='Accent.TButton')
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_button = ttk.Button(button_frame, text="❌ キャンセル", command=self.cancel_operation, 
                                       state='disabled')
        self.cancel_button.grid(row=0, column=1)
        
        # 入力ファイル変更時のイベント
        self.input_file.trace('w', self.on_input_file_change)
    
    def select_input_file(self):
        """入力ファイル選択"""
        logging.debug("ファイル選択ダイアログを表示")
        filename = filedialog.askopenfilename(
            title="MP3ファイルを選択",
            filetypes=[("MP3ファイル", "*.mp3"), ("音声ファイル", "*.mp3 *.wav *.m4a"), ("すべてのファイル", "*.*")]
        )
        if filename:
            logging.info(f"入力ファイルを選択: {filename}")
            self.input_file.set(filename)
            # 出力フォルダが未設定の場合、入力ファイルと同じフォルダを設定
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(filename))
                logging.debug(f"出力フォルダを自動設定: {os.path.dirname(filename)}")
            # 設定を保存
            self.save_current_settings()
    
    def select_output_dir(self):
        """出力フォルダ選択"""
        directory = filedialog.askdirectory(title="出力フォルダを選択")
        if directory:
            self.output_dir.set(directory)
            # 設定を保存
            self.save_current_settings()
    
    def on_input_file_change(self, *args):
        """入力ファイル変更時の処理"""
        filepath = self.input_file.get()
        if filepath and os.path.exists(filepath):
            try:
                logging.debug(f"音声ファイルの情報を読み込み開始: {filepath}")
                # ファイル名をエンコード
                encoded_path = str(Path(filepath).resolve())
                logging.debug(f"エンコードされたパス: {encoded_path}")
                
                # 一時ファイルを作成
                temp_dir = os.path.join(script_dir, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                temp_file = os.path.join(temp_dir, 'temp_audio.wav')
                
                # FFmpegで変換
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', encoded_path,
                    '-acodec', 'pcm_s16le',
                    '-vn',
                    '-f', 'wav',
                    temp_file
                ]
                logging.debug(f"FFmpegコマンド: {' '.join(ffmpeg_cmd)}")
                
                result = subprocess.run(ffmpeg_cmd, 
                                     capture_output=True, 
                                     encoding=SYSTEM_ENCODING,
                                     errors='replace',
                                     check=True)
                logging.debug(f"FFmpeg出力: {result.stdout}")
                
                # 変換したファイルを読み込み
                audio = AudioSegment.from_file(temp_file)
                duration_seconds = len(audio) / 1000
                duration_minutes = duration_seconds / 60
                duration_hours = duration_minutes / 60
                
                file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                
                if duration_hours >= 1:
                    duration_text = f"{int(duration_hours)}時間{int(duration_minutes % 60)}分"
                else:
                    duration_text = f"{int(duration_minutes)}分{int(duration_seconds % 60)}秒"
                
                info_text = f"📊 再生時間: {duration_text} | ファイルサイズ: {file_size:.1f}MB"
                self.info_label.config(text=info_text)
                logging.info(f"音声ファイル情報取得成功 - 再生時間: {duration_text}, サイズ: {file_size:.1f}MB")
                
                # 一時ファイルを削除
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logging.warning(f"一時ファイルの削除に失敗: {str(e)}")
                
            except subprocess.CalledProcessError as e:
                error_msg = f"FFmpegの処理に失敗: {e.stderr}"
                logging.error(error_msg)
                self.info_label.config(text="⚠️ ファイル情報を読み取れませんでした")
                messagebox.showerror("エラー", error_msg)
            except Exception as e:
                logging.error(f"ファイル情報の読み取りに失敗: {str(e)}", exc_info=True)
                self.info_label.config(text="⚠️ ファイル情報を読み取れませんでした")
                messagebox.showerror("エラー", f"ファイルの読み取りに失敗しました：\n{str(e)}")
        else:
            self.info_label.config(text="ファイルを選択してください")
            logging.debug("ファイルが選択されていないか、存在しません")
    
    def start_splitting(self):
        """分割処理開始"""
        if not self.validate_inputs():
            return
        
        # UI状態変更
        self.start_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.progress_bar.config(value=0)
        self.progress_label.config(text="準備中...")
        
        # バックグラウンドで処理実行
        self.current_operation = threading.Thread(target=self.split_audio_thread)
        self.current_operation.daemon = True
        self.current_operation.start()
    
    def validate_inputs(self):
        """入力値の検証"""
        if not self.input_file.get():
            messagebox.showerror("エラー", "入力ファイルを選択してください")
            return False
        
        if not os.path.exists(self.input_file.get()):
            messagebox.showerror("エラー", "入力ファイルが見つかりません")
            return False
        
        if not self.output_dir.get():
            messagebox.showerror("エラー", "出力フォルダを選択してください")
            return False
        
        if self.split_duration.get() <= 0:
            messagebox.showerror("エラー", "分割時間は1分以上で設定してください")
            return False
        
        return True
    
    def split_audio_thread(self):
        """分割処理（バックグラウンド）"""
        try:
            input_path = self.input_file.get()
            output_path = self.output_dir.get()
            duration_minutes = self.split_duration.get()
            
            logging.info(f"分割処理開始 - 入力: {input_path}, 出力: {output_path}, 分割時間: {duration_minutes}分")
            
            # 出力ディレクトリ作成
            os.makedirs(output_path, exist_ok=True)
            
            # 進捗更新
            self.progress_queue.put(("progress", 10, "音声ファイルを読み込み中..."))
            
            # 音声ファイル読み込み
            logging.debug("音声ファイルの読み込み開始")
            audio = AudioSegment.from_file(input_path)
            logging.debug("音声ファイルの読み込み完了")
            
            # 分割計算
            chunk_duration_ms = duration_minutes * 60 * 1000
            total_chunks = int(len(audio) / chunk_duration_ms) + (1 if len(audio) % chunk_duration_ms > 0 else 0)
            
            logging.info(f"分割数: {total_chunks}個")
            
            # ファイル名準備
            input_filename = Path(input_path).stem
            
            self.progress_queue.put(("progress", 20, f"{total_chunks}個のファイルに分割します"))
            
            # 分割処理
            for i in range(total_chunks):
                if getattr(self.current_operation, '_stop_requested', False):
                    logging.info("処理がキャンセルされました")
                    self.progress_queue.put(("error", "処理がキャンセルされました"))
                    return
                
                start_time = i * chunk_duration_ms
                end_time = min((i + 1) * chunk_duration_ms, len(audio))
                
                chunk = audio[start_time:end_time]
                
                # 出力ファイル名
                output_filename = f"{input_filename}_part{i+1:02d}.mp3"
                output_file_path = os.path.join(output_path, output_filename)
                
                logging.debug(f"分割ファイル作成中: {output_filename}")
                
                # 進捗更新
                progress = 20 + (i / total_chunks) * 70
                self.progress_queue.put(("progress", progress, f"分割中... ({i+1}/{total_chunks})"))
                
                # エクスポート設定
                export_params = {"format": "mp3"}
                if self.preserve_quality.get():
                    export_params["bitrate"] = "320k"
                
                chunk.export(output_file_path, **export_params)
                logging.debug(f"分割ファイル作成完了: {output_filename}")
            
            logging.info("分割処理が正常に完了")
            self.progress_queue.put(("progress", 100, "完了！"))
            self.progress_queue.put(("success", f"✅ 分割完了！ {total_chunks}個のファイルが作成されました"))
            
            # フォルダを開く
            if self.auto_open_folder.get():
                self.open_output_folder()
                
        except Exception as e:
            logging.error(f"分割処理中にエラーが発生: {str(e)}", exc_info=True)
            self.progress_queue.put(("error", f"エラーが発生しました: {str(e)}"))
    
    def cancel_operation(self):
        """処理キャンセル"""
        if self.current_operation and self.current_operation.is_alive():
            self.current_operation._stop_requested = True
            self.reset_ui_state()
    
    def reset_ui_state(self):
        """UI状態リセット"""
        self.start_button.config(state='normal')
        self.cancel_button.config(state='disabled')
        self.progress_bar.config(value=0)
        self.progress_label.config(text="")
    
    def open_output_folder(self):
        """出力フォルダを開く"""
        output_path = self.output_dir.get()
        if os.path.exists(output_path):
            if sys.platform == "win32":
                os.startfile(output_path)
            elif sys.platform == "darwin":
                os.system(f"open '{output_path}'")
            else:
                os.system(f"xdg-open '{output_path}'")
    
    def check_progress(self):
        """進捗チェック（定期実行）"""
        try:
            while True:
                msg_type, *data = self.progress_queue.get_nowait()
                
                if msg_type == "progress":
                    progress, text = data
                    self.progress_bar.config(value=progress)
                    self.progress_label.config(text=text)
                
                elif msg_type == "success":
                    message = data[0]
                    self.progress_label.config(text=message, style='Success.TLabel')
                    self.reset_ui_state()
                    messagebox.showinfo("完了", message)
                
                elif msg_type == "error":
                    message = data[0]
                    self.progress_label.config(text=f"❌ {message}", style='Error.TLabel')
                    self.reset_ui_state()
                    messagebox.showerror("エラー", message)
        
        except queue.Empty:
            pass
        
        # 100ms後に再チェック
        self.root.after(100, self.check_progress)

    def save_current_settings(self):
        """現在の設定を保存"""
        settings = {
            'input_file': self.input_file.get(),
            'output_dir': self.output_dir.get(),
            'split_duration': self.split_duration.get(),
            'preserve_quality': self.preserve_quality.get(),
            'auto_open_folder': self.auto_open_folder.get()
        }
        save_settings(settings)


def main():
    """メイン関数"""
    try:
        logging.info("アプリケーション初期化開始")
        from pydub import AudioSegment
    except ImportError:
        logging.error("pydubライブラリがインストールされていません")
        messagebox.showerror("エラー", "pydubライブラリがインストールされていません。\n\npip install pydub\n\nを実行してください。")
        return
    
    root = Tk()
    app = AudioSplitterGUI(root)
    
    # ウィンドウを中央に配置
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = root.winfo_width()
    window_height = root.winfo_height()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"+{x}+{y}")
    
    logging.info("メインループ開始")
    root.mainloop()


if __name__ == "__main__":
    main()