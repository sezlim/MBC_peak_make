from tkinter import font as tkFont

import win32gui
import re
import psutil
import shutil
import os
from pathlib import Path
import time
import win32process
import win32api
import win32con
import threading
from typing import Union
from tkinter import ttk  # 콤보박스(Dropdown)용 모듈
import pyautogui

import socket
import datetime
import ctypes
import tkinter as tk
from tkinter import messagebox
import config
import part2_sync
import part3_import_upload
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional
import random

################ 글로벌 변수 정의

premiere_hwnd = 0
current_file_path = ""
root = ""
status_text_var = None
btn_start = None
btn_cancel = None
running_thread = None  # 현재 실행 중인 스레드를 저장
combo_pgm = None
combo_scan_day = None
stop_flag = threading.Event()  # 작업을 중지시키기 위한 플래그 (이벤트 객체)

##################### 탐색 부분에 관한 변수##########


day_before_scan = config.scan_day


##################### 탐색 부분에 관한 변수 ##########


##################################################


############################################
def is_mxf_over_limit(file_path: str, limit_hours: float) -> bool:
    """
    ffprobe를 사용하여 MXF 파일의 길이가 지정된 시간(limit_hours)을 초과하는지 확인합니다.

    Args:
        file_path (str): 파일 경로
        limit_hours (float): 제한할 시간 (예: 10, 2.5 등)

    Returns:
        bool: 제한 시간을 초과하면 True, 아니면 False
    """

    # 1. 파일이 MXF인지 확인
    if not str(file_path).lower().endswith('.mxf'):
        return False

    # 2. ffprobe 위치 찾기
    ffprobe_exe = find_ffprobe_path()
    if not ffprobe_exe:
        print("❌ ffprobe를 찾을 수 없어 길이 체크를 건너뜁니다.")
        return False

    # 3. 명령어 준비
    cmd = [
        str(ffprobe_exe),
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(file_path)
    ]

    try:
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            creationflags=creation_flags
        )

        duration_str = result.stdout.strip()
        if not duration_str:
            return False

        duration_seconds = float(duration_str)

        # --- [변경점] 입력받은 시간을 초 단위로 변환하여 비교 ---
        limit_seconds = limit_hours * 3600  # 1시간 = 3600초

        if duration_seconds > limit_seconds:
            print(f"⚠️ [제한 초과] {limit_hours}시간보다 긴 파일: {duration_seconds / 3600:.2f}시간 ({file_path})")
            return True

    except Exception as e:
        print(f"⚠️ 길이 확인 중 오류 발생: {e}")
        return False

    return False


def make_folder(target_path):
    try:
        # os.makedirs()는 경로상의 모든 중간 디렉터리도 함께 생성합니다.
        # exist_ok=True 옵션이 핵심입니다.
        os.makedirs(target_path, exist_ok=True)
        print(f"폴더 생성 또는 확인 완료: {target_path}")
    except OSError as e:
        # UNC 경로에 대한 권한 문제 등으로 인해 생성에 실패할 경우 에러 처리
        print(f"오류: 폴더 생성에 실패했습니다. 경로/권한을 확인하세요: {e}")


############################################
def get_pgm_number_from_path(ingest_file_path: str) -> str | None:
    """
    경로 문자열에서 '\MASTER\' 뒤에 나오는 'PGMXX' 형태의 폴더 이름을 추출합니다.

    Args:
        ingest_file_path (str): 분석할 파일 또는 폴더 경로.

    Returns:
        str | None: 추출된 PGMXX 문자열 (예: 'PGM00') 또는 찾지 못했을 경우 None.
    """
    # 1. 경로 구분자를 운영체제에 맞게 정규화 (\ 또는 /)
    #    -> Windows 경로는 os.sep 대신 \\를 명시적으로 사용하거나, /로 통일하는 것이 정규식에서 안전함
    #       (단, 입력이 \\npsmain... 형태이므로 \\를 기준으로 패턴을 만듦)

    # 2. 정규식 패턴 설명:
    #    - r'': Raw string으로 백슬래시를 이스케이프하지 않음.
    #    - \\MASTER\\: '\\MASTER\\' 문자열을 정확히 찾음. (경로에서 \\는 \를 의미)
    #    - (PGM\d{2}): 캡처 그룹(Group 1)으로 'PGM' 뒤에 숫자 두 자리(00~99)가 오는 패턴을 찾음.
    pattern = r'\\MASTER\\(PGM\d{2})'

    # 3. 대소문자 구분 없이 검색 (flags=re.IGNORECASE)
    match = re.search(pattern, ingest_file_path, flags=re.IGNORECASE)

    if match:
        # Group 1 (PGMXX)을 반환
        return match.group(1)
    else:
        return None


def rename_file_extension(original_path: Union[str, Path], new_ext: str) -> bool:
    """
    주어진 파일 경로의 확장자를 새 확장자로 변경하고, 실제 파일의 이름까지 변경합니다.

    Args:
        original_path (str | Path): 확장자를 변경할 원본 파일 경로 (문자열 또는 Path 객체).
        new_ext (str): 변경할 새 확장자 (예: ".finish"). 점(.)으로 시작해야 합니다.

    Returns:
        bool: 파일 이름 변경 성공 여부 (True: 성공, False: 실패).
    """

    # Path 객체로 변환하여 파일 존재 여부 확인
    old_path = Path(original_path)
    if not old_path.exists():
        print(f"❌ 오류: 원본 파일을 찾을 수 없습니다: {old_path}")
        return False

    # 새 확장자가 점으로 시작하지 않으면 추가 (안전성 확보)
    if not new_ext.startswith('.'):
        new_ext = '.' + new_ext

    # --- 1. 새 경로 문자열 생성 (rsplit을 사용한 안전한 확장자 변경) ---
    original_path_str = str(old_path)

    # 마지막 점(.)을 기준으로 한 번만 분리하여 확장자 부분만 대체
    parts = original_path_str.rsplit('.', 1)

    if len(parts) > 1:
        # 확장자를 제외한 부분 + 새 확장자
        new_file_path_str = parts[0] + new_ext
    else:
        # 확장자가 없는 경우 (파일 이름 뒤에 새 확장자를 붙임)
        new_file_path_str = original_path_str + new_ext

    # 새 Path 객체 생성
    new_path = Path(new_file_path_str)

    # --- 2. 실제 파일 이름 변경 (Rename 실행) ---
    try:
        # Path.rename() 메서드를 사용하여 실제 파일 이름을 변경합니다.
        old_path.rename(new_path)

        print(f"✅ 파일 이름 변경 성공!")
        print(f"원본: {old_path.name}")
        print(f"변경: {new_path.name}")
        return True

    except Exception as e:
        print(f"❌ 파일 이름 변경 실패: {e}")
        return False


def check_import_status(file_path: str, target_char: str) -> bool:
    """
    주어진 파일 경로의 내용을 읽어, 콤마로 구분된 두 번째 필드에
    특정 문자(예: 'r')가 포함되어 있는지 확인합니다.

    Args:
        file_path (str): 내용을 읽을 .txt 파일의 전체 경로.
        target_char (str): 찾으려는 문자 (예: 'r').

    Returns:
        bool: 특정 문자가 해당 위치에 있으면 True, 아니면 False.
    """
    try:
        # 파일을 읽어서 첫 번째 줄만 사용합니다.
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.readline().strip()

        if not content:
            # 파일 내용이 비어있으면 False 반환
            return False

        # 콤마(,)를 기준으로 문자열을 분리합니다.
        parts = content.split(',')

        # 'C:/1234.png', 'i', 'y (Success: ...)' 와 같이 3개 이상으로 분리됩니다.
        if len(parts) >= 2:
            # 두 번째 필드 (인덱스 1)를 가져옵니다. (예: 'i' 또는 'r')
            status_char = parts[1].strip().lower()  # 공백 제거 및 소문자 변환

            # 찾으려는 문자(target_char)와 일치하는지 확인합니다.
            return status_char == target_char.lower()

        else:
            # 예상한 형식(콤마로 구분된 2개 이상의 필드)이 아니면 False 반환
            return False

    except FileNotFoundError:
        print(f"❌ 오류: 파일을 찾을 수 없습니다: {file_path}")
        return False
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def clear_subfolders_in_cache(cache_path: Union[str, Path], excluded_folders: list[str] = None) -> bool:
    """
    주어진 경로의 하위 항목을 삭제합니다.
    - excluded_folders에 포함된 폴더는 내용물만 삭제되어 빈 폴더로 유지됩니다.
    - 그 외의 하위 폴더는 폴더 자체와 내용물이 모두 삭제됩니다.

    Args:
        cache_path (str | Path): 캐시 폴더의 경로 (예: C:\Adobe_Cache).
        excluded_folders (List[str], optional): 내용물만 삭제하고 폴더 자체는 유지할 목록. 기본값 None.

    Returns:
        bool: 삭제 작업 성공 여부.
    """

    root_path = Path(cache_path).resolve()

    if excluded_folders is None:
        excluded_folders = []

    if not root_path.is_dir():
        print(f"❌ 오류: 폴더를 찾을 수 없거나 접근할 수 없습니다: {root_path}")
        return False

    excluded_set = {name.lower() for name in excluded_folders}

    print(f"--- {root_path} 하위 내용물 삭제 시작 ---")
    print(f"--- 유지 (빈 폴더로): {excluded_set if excluded_set else '없음'} ---")

    success_count = 0
    failure_count = 0

    # root_path의 바로 아래 항목들만 순회합니다. (1단계 하위 항목)
    for item in root_path.iterdir():
        item_name_lower = item.name.lower()

        try:
            is_excluded = item_name_lower in excluded_set

            if item.is_dir():

                if is_excluded:
                    # 1. 예외 대상 폴더인 경우: 내용물만 삭제 (폴더 구조 유지)
                    print(f"➡️ 내용물 삭제 시작: {item.name} (폴더는 유지)")

                    # 해당 폴더 내부를 순회하며 파일/폴더 삭제
                    for sub_item in item.iterdir():
                        if sub_item.is_dir():
                            shutil.rmtree(sub_item)
                        elif sub_item.is_file():
                            os.remove(sub_item)

                    print(f"✅ 빈 폴더로 유지 완료: {item.name}")
                    success_count += 1

                else:
                    # 2. 삭제 대상 폴더인 경우: 폴더와 내용물 전체 삭제
                    shutil.rmtree(item)
                    print(f"✅ 폴더 전체 삭제 완료: {item.name}")
                    success_count += 1

            elif item.is_file():
                # 3. 파일인 경우: 예외 목록에 폴더명이 아닌 파일명이 들어갈 수도 있으므로 확인 (일반적으로는 파일은 모두 삭제)
                if not is_excluded:
                    os.remove(item)
                    print(f"✅ 파일 삭제 완료: {item.name}")
                    success_count += 1
                else:
                    # 파일이지만 예외 목록에 포함된 경우 (파일 자체를 유지)
                    print(f"➡️ 파일 유지: {item.name} (예외 목록에 포함되어 건너뜀)")

        except Exception as e:
            # 권한 문제 등으로 삭제 실패 시
            print(f"❌ 삭제 실패: {item.name} -> {e}")
            failure_count += 1

    print("--- 삭제 작업 완료 ---")
    print(f"성공: {success_count}개, 실패: {failure_count}개")

    return failure_count == 0


def count_pek_file_and_return_list(root_path):
    """
    지정된 경로와 모든 하위 폴더에서 .pek 파일의 총 개수와 전체 경로 목록을 반환합니다.

    Args:
        root_path: 검색을 시작할 루트 경로.

    Returns:
        (pek_count, pek_file_paths) 튜플:
        - pek_count: 발견된 .pek 파일의 총 개수 (int)
        - pek_file_paths: 발견된 모든 .pek 파일의 전체 경로 목록 (list[str])
    """
    pek_count = 0
    pek_file_paths = []  # <--- 전체 경로를 저장할 리스트 추가

    # os.walk를 사용하여 root_path 아래의 모든 폴더를 순회합니다.
    for dirpath, dirnames, filenames in os.walk(root_path):
        # 현재 폴더의 파일 목록(filenames)을 확인합니다.
        for filename in filenames:
            # 파일 이름이 .pek으로 끝나는지 확인합니다.
            if filename.lower().endswith('.pek'):
                # 1. 파일 개수 증가
                pek_count += 1

                # 2. 파일의 전체 경로를 생성하여 리스트에 추가
                # os.path.join(현재 폴더 경로, 파일 이름)
                full_path = os.path.join(dirpath, filename)
                pek_file_paths.append(full_path)

        # (선택 사항) 개수를 빠르게 확인해야 한다면, 2개 이상이 되는 순간 탐색을 멈출 수 있습니다.
        # if pek_count >= 2:
        #     return pek_count, pek_file_paths # 즉시 반환하여 성능 최적화

    # 개수와 경로 리스트를 튜플 형태로 반환합니다.
    return pek_count, pek_file_paths


def find_ffprobe_path() -> Optional[Path]:
    """
    Python 실행 파일의 위치부터 시작하여 모든 하위 폴더를 재귀적으로 탐색하여 ffprobe 실행 파일을 찾습니다.
    """
    # Python 실행 파일(.exe)이 위치한 폴더 (검색 시작 지점)
    start_dir = Path(sys.executable).parent
    ffprobe_name = 'ffprobe.exe' if sys.platform.startswith('win') else 'ffprobe'

    print(f"🔍 ffprobe 검색 시작: {start_dir}")
    print(f"🎯 찾을 파일: {ffprobe_name}")

    # rglob()을 사용하여 시작 폴더 아래의 모든 항목을 재귀적으로 탐색
    for item in start_dir.rglob(ffprobe_name):
        if item.is_file():
            print(f"✅ ffprobe 발견 위치: {item}")
            return item

    # 추가적으로, PATH 환경 변수에서도 검색 (이전 코드 유지)
    try:
        # 'where' (Windows) 또는 'which' (Linux/macOS) 명령을 사용하여 PATH 검색
        result = subprocess.run(
            ['where' if sys.platform.startswith('win') else 'which', ffprobe_name],
            capture_output=True, text=True, check=True
        )
        path_result = Path(result.stdout.strip().split('\n')[0])
        print(f"✅ ffprobe PATH에서 발견 위치: {path_result}")
        return path_result
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"❌ ffprobe를 {start_dir}의 하위 폴더나 PATH에서 찾지 못했습니다.")
        return None


def is_file_silent(ingest_file_path: str, threshold_dbfs: int = -50) -> bool:
    """
    주어진 파일에 오디오 트랙이 존재하는지 ffprobe를 사용하여 확인합니다.
    (실제 신호 레벨 검사는 하지 않음. 오직 오디오 트랙 유무만 판단).

    Args:
        ingest_file_path (str): 검사할 미디어 파일 경로.
        threshold_dbfs (int): (이 함수에서는 사용되지 않음. 호환성을 위해 유지).

    Returns:
        bool: 오디오 트랙이 없으면 True (무음 간주), 있으면 False.
    """
    file_path = Path(ingest_file_path)

    if not file_path.exists():
        print(f"❌ Error: File not found: {ingest_file_path}")
        return False

    ffprobe_path = find_ffprobe_path()
    if not ffprobe_path:
        print("❌ Error: ffprobe executable not found. Please ensure ffmpeg is installed and accessible.")
        return False

    # ffprobe 명령 구성
    command = [
        str(ffprobe_path),
        '-v', 'error',
        '-select_streams', 'a',
        '-show_streams',
        '-of', 'json',
        str(file_path)
    ]

    # 윈도우에서 CMD 창이 뜨지 않도록 STARTUPINFO 설정
    startupinfo = None
    if sys.platform.startswith('win'):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        # ffprobe 실행
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            startupinfo=startupinfo
        )

        # JSON 출력 파싱
        if not result.stdout.strip():
            has_audio = False
        else:
            info = json.loads(result.stdout)
            has_audio = len(info.get('streams', [])) > 0

        if has_audio:
            # print(f"✅ 오디오 트랙 발견. 무음이 아님.")
            return False
        else:
            # print(f"✅ 오디오 트랙 없음. 무음으로 간주.")
            return True

    except Exception as e:
        print(f"❌ Error during ffprobe execution: {e}")
        return False


def terminate_program_by_hwnd(hwnd: int) -> bool:
    """
    주어진 HWND를 사용하여 해당 창을 소유한 프로세스를 강제로 종료합니다.

    Args:
        hwnd (int): 종료할 프로그램의 창 핸들.

    Returns:
        bool: 프로세스 종료 성공 여부.
    """
    if hwnd == 0:
        print("오류: 유효한 윈도우 핸들(HWND)이 아닙니다 (값: 0).")
        return False

    try:
        # 1. HWND에서 프로세스 ID(PID)를 얻어옵니다.
        # GetWindowThreadProcessId 함수는 스레드 ID와 PID를 반환합니다.
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        if pid == 0:
            print(f"오류: HWND {hwnd}에 연결된 프로세스 ID(PID)를 찾을 수 없습니다.")
            return False

        # 2. PID를 사용하여 프로세스 핸들을 엽니다.
        # PROCESS_TERMINATE 권한만 요청합니다.
        process_handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)

        if process_handle == 0:
            print(f"오류: PID {pid}의 프로세스를 열 수 없습니다. (권한 문제일 수 있음)")
            return False

        # 3. 프로세스를 강제로 종료합니다. (Exit Code 0)
        # 이 함수는 프로세스를 즉시 종료시키며, 저장되지 않은 데이터는 손실됩니다.
        win32api.TerminateProcess(process_handle, 0)

        print(f"✅ PID {pid} (HWND {hwnd} 소유) 프로세스를 강제로 종료했습니다.")
        return True

    except win32api.error as e:
        print(f"Windows API 오류 발생 (코드 {e.winerror}): {e.strerror}")
        return False
    except Exception as e:
        print(f"알 수 없는 오류 발생: {e}")
        return False


def check_and_prompt_premiere_shutdown():
    """
    실행 중인 Adobe Premiere Pro (모든 버전)를 찾아
    사용자에게 종료 여부를 묻는 팝업을 띄웁니다.

    Returns:
        bool: 사용자가 '예'를 눌러 종료를 시도했으면 True,
              아니거나 프로세스가 없으면 False를 반환합니다.
    """

    # 1. 찾으려는 프로세스 이름의 핵심 부분 (소문자, 공백/exe 제거)
    target_prefix = "adobe premiere pro"
    target_prefix = target_prefix.lower().replace(" ", "").replace(".exe", "")

    found_proc = None

    # 2. 모든 실행 중인 프로세스 검사
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # 3. 프로세스 이름 정리
            # 예: "Adobe Premiere Pro 2024.exe" -> "adobepremierepro2024"
            proc_name = proc.info['name']
            clean_proc_name = proc_name.lower().replace(" ", "").replace(".exe", "")

            # 4. 핵심 이름으로 "시작"하는지 확인 (2024, 2025 등 모든 버전 일치)
            if clean_proc_name.startswith(target_prefix):
                found_proc = proc  # 일치하는 프로세스 저장
                break  # 하나만 찾으면 중단

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass  # 접근할 수 없는 프로세스는 무시

    # 5. 일치하는 프로세스를 찾은 경우
    if found_proc:
        # 팝업을 띄우기 위한 임시 Tkinter 루트 윈도우 생성 (숨김)
        root = tk.Tk()
        root.withdraw()

        # 팝업 메시지 표시
        response = messagebox.askyesno(
            "프로세스 발견",
            f"'{found_proc.info['name']}'이(가) 이미 실행 중입니다. \n\n\n <피크생성기 프로그램>이 직접 실행해야 작업이 가능합니다 \n\n\n 강제종료 후 직접 실행하게 하겠습니까?"
        )

        # 임시 루트 윈도우 제거
        root.destroy()

        # 6. 사용자가 '예'를 선택한 경우
        if response:
            try:
                found_proc.terminate()  # 정상 종료 시도
                print(f"✅ 성공: '{found_proc.info['name']}' 프로세스를 종료했습니다.")
                return True
            except psutil.Error as e:
                print(f"❌ 오류: 프로세스 종료 실패: {e}")
                return False
        else:
            print("정보: 사용자가 '아니요'를 선택했습니다.")
            return False

    # 7. 일치하는 프로세스를 찾지 못한 경우
    else:
        print("정보: 실행 중인 Adobe Premiere Pro 프로세스를 찾지 못했습니다.")
        return True


def find_all_program_hwnds_robust(process_name: str) -> list[int]:
    """
    프로세스 이름으로 해당하는 모든 최상위 윈도우 핸들(list[int])을 찾습니다.
    (기존 find_program_hwnd_robust 로직 기반, 목록을 반환하도록 수정)
    """
    clean_target_name = process_name.lower().replace(" ", "").replace(".exe", "")

    target_pids = set()
    # 1. PID 검색 (기존 로직 유지)
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_name = proc.info['name'].lower().replace(" ", "").replace(".exe", "")
            if proc_name == clean_target_name:
                target_pids.add(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not target_pids:
        print(f"정보: '{process_name}' 이름의 실행 중인 프로세스를 찾을 수 없습니다.")
        return []

    hwnds_found = []

    def enum_windows_callback(hwnd, _):
        """ EnumWindows 콜백 """
        if win32gui.GetParent(hwnd) != 0:
            return True  # 자식 윈도우 건너뜀

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except:
            return True  # PID를 가져올 수 없으면 건너뜀

        if pid in target_pids:
            # PID가 일치하고, '제목'이 있는 창이면 메인 윈도우 또는 주요 팝업으로 간주
            if win32gui.GetWindowText(hwnd):
                hwnds_found.append(hwnd)

                # ★★★ 핵심 수정: return False 대신 True로 변경하여 모든 창을 찾도록 함 ★★★
                return True

        return True  # 다음 창으로 계속 진행

    try:
        win32gui.EnumWindows(enum_windows_callback, None)
    except Exception:
        pass  # EnumWindows 실행 중 발생한 예외 무시

    if hwnds_found:
        return hwnds_found
    else:
        print(f"정보: '{process_name}' 프로세스는 실행 중이나, 적절한 윈도우를 찾을 수 없습니다.")
        return []


def find_all_program_hwnds(exe_name: str) -> list[int]:
    """
    특정 프로세스 이름(exe_name)에 해당하는 모든 최상위 창의 핸들 목록을 반환합니다.

    Args:
        exe_name: 찾고자 하는 프로그램의 실행 파일 이름 (예: "Adobe Premiere Pro.exe")

    Returns:
        해당 프로세스에 속하는 모든 최상위 창 핸들(HWND)의 리스트.
    """

    # 1. exe_name에 해당하는 모든 프로세스 ID(PID)를 찾습니다.
    target_pids = set()
    try:
        # psutil을 사용하여 프로세스 이름으로 PID를 찾습니다.
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] == exe_name:
                target_pids.add(proc.info['pid'])
    except Exception as e:
        # psutil 사용 중 오류가 발생하거나 설치되지 않은 경우
        print(f"경고: psutil 사용 중 오류 발생 ({e}). 수동으로 PID를 찾습니다.")
        # 이 부분은 win32api.EnumProcesses 등을 사용하여 복잡하게 구현해야 하지만,
        # psutil이 가장 간편하고 정확합니다. psutil이 없으면 이 함수는 작동하지 않을 수 있습니다.
        pass

    if not target_pids:
        # 해당 프로세스가 실행 중이 아니면 빈 리스트 반환
        return []

    hwnds = []

    # 3. 모든 최상위 창을 순회하며 PID가 일치하는 창의 핸들을 추가합니다.
    # win32gui.EnumWindows는 모든 최상위 창을 순회하며 콜백 함수를 호출합니다.
    def callback(hwnd, extra):
        # 창이 보이는 상태이고 (win32gui.IsWindowVisible), 메인 창일 가능성이 높은 창만 처리
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetParent(hwnd) == 0:
            try:
                # 2. 각 창의 PID를 확인합니다.
                _, pid = win32process.GetWindowThreadProcessId(hwnd)

                # 해당 창의 PID가 우리가 찾는 PID 목록에 있는지 확인
                if pid in target_pids:
                    hwnds.append(hwnd)
            except Exception:
                # PID를 가져올 수 없는 경우 무시 (보통 시스템 창)
                pass
        return True  # 다음 창으로 계속 진행

    win32gui.EnumWindows(callback, None)

    # 4. 리스트 반환
    return hwnds


def get_premiere_hwnds() -> list[int]:
    """
    현재 실행 중인 모든 유효한 Premiere Pro 창의 핸들 목록을 반환합니다.
    (팝업/대화 상자를 제외하고 메인 창만 필터링하도록 강화)
    """
    PROGRAM_NAME = "Adobe Premiere Pro.exe"

    # 1. 모든 핸들을 검색합니다. (여기서 find_all_program_hwnds_robust를 사용)
    # 이 함수는 이미 GetParent(hwnd) == 0 및 GetWindowText(hwnd) != "" 필터링이 적용되어 있습니다.
    all_hwnds = find_all_program_hwnds_robust(PROGRAM_NAME)

    if not all_hwnds:
        return []

    # 2. 메인 창만 남기도록 추가 필터링 (창 제목을 사용하여 팝업을 제외)
    # Premiere Pro의 메인 창 제목에는 'Premiere Pro'와 '프로젝트 이름'이 포함됩니다.
    # 팝업 창 제목에는 보통 'Premiere Pro'라는 문구가 없습니다. (예: '새 프로젝트' 또는 '저장')
    main_window_hwnds = []

    for hwnd in all_hwnds:
        title = win32gui.GetWindowText(hwnd)

        # 'Premiere Pro'라는 문구가 포함된 창 제목만 메인 창으로 간주
        # 이 조건은 대부분의 프로젝트 파일이 열려있는 메인 창을 정확하게 잡아냅니다.
        if "Premiere Pro" in title:
            main_window_hwnds.append(hwnd)

        # (선택 사항) 만약 'Premiere Pro'라는 이름이 들어간 팝업이 있다면,
        # class name ('PremierePro')을 추가로 확인하여 더 정확하게 필터링할 수 있습니다.
        # elif win32gui.GetClassName(hwnd) == "PremierePro":
        #     main_window_hwnds.append(hwnd)

    # 필터링된 메인 창 목록 반환
    if main_window_hwnds:
        return main_window_hwnds
    else:
        # 제목 필터링 후에도 결과가 없다면, 모든 핸들(팝업 포함 가능성 있음)을 반환하여
        # 혹시 모를 상황에 대비하거나, 아니면 빈 리스트를 반환합니다.
        # 여기서는 안전하게 빈 리스트를 반환합니다.
        return []


############################################################################################################3
def update_status_file(target_folder: str, refresh_time_min=20) -> bool:
    """
    target_folder에 status.txt 파일을 생성 또는 업데이트합니다.

    - 파일이 없거나 TIMESTAMP가 refresh_time_min보다 오래되었으면 True 반환 및 업데이트.
    - TIMESTAMP가 refresh_time_min 이내이면 False 반환 및 업데이트 없음.

    Args:
        target_folder (str): status.txt 파일이 위치할 폴더 경로.
        refresh_time_min (int): 파일을 업데이트할 최소 시간 간격 (분).

    Returns:
        bool: 파일이 업데이트되었으면 True, 아니면 False.
    """
    file_path = os.path.join(target_folder, "status.txt")

    # 1. PC 정보 및 현재 시간 준비
    pc_name, ip_address = config.get_pc_info()
    current_time = datetime.datetime.now()
    time_format = "%Y-%m-%d %H:%M:%S"

    should_update = False

    if os.path.exists(file_path):
        try:
            # 2. 기존 파일 내용 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 3. <TIME_STAMP> 값 추출 (정규표현식 사용)
            match = re.search(r"<TIME_STAMP>(.*?)</TIME_STAMP>", content)

            if match:
                # 추출된 문자열을 datetime 객체로 변환
                timestamp_str = match.group(1).strip()
                recorded_time = datetime.datetime.strptime(timestamp_str, time_format)

                # 4. 시간 차이 계산
                time_difference = current_time - recorded_time
                refresh_delta = datetime.timedelta(minutes=refresh_time_min)

                # 5. 업데이트 필요 여부 판단
                if time_difference >= refresh_delta:
                    should_update = True
                # else: should_update는 이미 False

            else:
                # TIMESTAMP 태그가 파일에 없으면 업데이트 필요
                should_update = True

        except Exception as e:
            print(f"Error reading or parsing status.txt: {e}")
            # 파일 읽기/파싱 오류 시에도 업데이트를 시도
            should_update = True
    else:
        # 파일이 존재하지 않으면 업데이트 필요
        should_update = True

    # 6. 업데이트가 필요한 경우 파일에 새 내용 작성
    if should_update:
        current_time_str = current_time.strftime(time_format)

        content_in_txt = f"""
<PC_NAME>{pc_name}</PC_NAME>
<IP_ADDRESS>{ip_address}</IP_ADDRESS>
<TIME_STAMP>{current_time_str}</TIME_STAMP>
"""
        # 폴더가 없으면 생성
        os.makedirs(target_folder, exist_ok=True)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_in_txt.strip())
            return True
        except Exception as e:
            print(f"Error writing to status.txt: {e}")
            return False  # 쓰기 실패 시 False 반환

    return False


##############################################################################


def worker_loop():
    """ 백그라운드에서 실행될 반복 작업 로직 """
    global stop_flag

    ### 한번 정리하고 시작 캐시폴더
    # local_adobe_cache_path = r"C:\Adobe_Cache"
    # clear_subfolders_in_cache(local_adobe_cache_path,["Media Cache Files","Media Cache","Peak Files","Analyzer Cache Files"])
    #

    # 예시: 1초마다 반복되는 루프
    stop_flag.clear()  # 작업 시작 시 플래그 초기화
    counter = 0
    need_to_optimize = True
    while not stop_flag.is_set():  # stop_flag가 설정되지 않은 동안 반복
        try:
            source_path = r"\\npsmain.mbcnps.com\ROOT\MASTER"
            target_path = r"\\npsmain.mbcnps.com\SYSTEMS\AME_PEAK_MAKE_FOLDER"
            folders_to_skip = ["ProjectShare", "ShareFolder", ".temp"]
            ext_list = ['.mxf', '.wav', '.mov', '.MXF', '.WAV', '.MOV','.txt']
            days_to_scan = int(day_before_scan)
            print(f"스캔데이 입니다. {days_to_scan}")

            print(f"작업 스레드 실행 중... (횟수: {counter})")
            # update_status(f"처리 중... {counter}번째 반복") # 상태 업데이트는 메인 스레드로 전달해야 하지만, 여기선 간단히 가정
            counter += 1
            config.cleanup_empty_folders(target_path)

            if need_to_optimize:
                if update_status_file(target_path):
                    print("폴더 싱크 들어갑니다.")
                    for add_path in config.pgm:
                        source_pgm_path = os.path.join(source_path, add_path)
                        target_pgm_path = os.path.join(target_path, add_path)
                        part2_sync.create_optimized_stubs(source_pgm_path, target_pgm_path, days_to_scan,
                                                          folders_to_skip, ext_list)

                need_to_optimize = False

            ## 스캔 폴더에 폴더 동기화 완료 (import 할 준비 완료)

            while True:
                status_text_var.set(f"작업 대상을 찾습니다..")
                counter += 1  ## 안에도 counter 있어야 할듯
                if counter % 100 == 0:  # 파일 100개 쯤 만들면
                    # [수정] 헬퍼 함수 호출 (핸들 목록을 반환)
                    config.terminate_premiere_process()
                    time.sleep(10)
                    try:
                        # 경로의 파일을 실행합니다.

                        config.launch_premiere_from_config()
                        time.sleep(10)

                    except FileNotFoundError:
                        print(f"오류: 파일을 찾을 수 없습니다: {config.startup_proj_path}")
                    except Exception as e:
                        print(f"파일 실행 중 오류 발생: {e}")
                    on_hide()

                making_time = None
                print("루프입니다.-1")
                ## (탐색할 폴더, 원소스 폴더)

                ingest_file_path, stem_file_path = part3_import_upload.find_first_target_path(target_path, source_path,
                                                                                              ext_list)
                if ingest_file_path == None:
                    need_to_optimize = True
                    print("100초 쉬고 다시한번 스캔합니다.")
                    time.sleep(100)
                    break
                else:
                    PGM_number = config.get_pgm_number_from_path(ingest_file_path)
                    ##### PGM 번호 가져오는 코드
                    nas_adobe_DB_cache_path = os.path.join(source_path, str(PGM_number))
                    nas_adobe_DB_cache_path = os.path.join(nas_adobe_DB_cache_path, "ShareFolder")
                    nas_adobe_DB_cache_path = os.path.join(nas_adobe_DB_cache_path, "UserFolder")
                    nas_adobe_DB_cache_path = os.path.join(nas_adobe_DB_cache_path, "Adobe_Cache")
                    nas_adobe_DB_cache_path = os.path.join(nas_adobe_DB_cache_path, "Media Cache")
                    os.makedirs(nas_adobe_DB_cache_path, exist_ok=True)
                    print(f"폴더 준비 완료: {nas_adobe_DB_cache_path}")

                    backup_nas_adobe_DB_cache_path = nas_adobe_DB_cache_path.replace("npsmain.mbcnps.com",
                                                                                     "npsbackup.mbcnps.com")
                    os.makedirs(backup_nas_adobe_DB_cache_path, exist_ok=True)
                    print(f"폴더 준비 완료: {backup_nas_adobe_DB_cache_path}")

                if is_mxf_over_limit(ingest_file_path, 10):
                    print("10시간 넘는 mxf는 프리미어 버그로 진행하지 않습니다.")
                    # 확장자를 .finish로 교체 (기존 확장자 .mxf가 사라지고 .finish가 됨)
                    print(f"{stem_file_path}의 확장자를 변경합니다.")

                    # Path 객체로 변환
                    p = Path(stem_file_path)

                    if p.exists():
                        # .finish로 이름 변경 실행
                        p.rename(p.with_suffix(".finish"))
                        print("파일 이름 변경 완료!")
                    else:
                        print("파일이 없습니다.")
                    continue

                else:
                    print("mxf가 아니거나 10시간 이하의 파일입니다.")

                # 함수 실행 및 결과 출력
                pc_name, ip_address = config.get_pc_info()
                # 1. 현재 시간을 datetime 객체로 가져옵니다.
                time_stamp = datetime.datetime.now()
                # 2. 시간을 문자열로 변환할 포맷을 정의합니다.
                time_format = "%Y-%m-%d %H:%M:%S"
                # 3. datetime 객체를 포맷에 맞는 문자열로 변환합니다. (strftime 사용)
                time_stamp = time_stamp.strftime(time_format)

                content_in_txt = f"""
                <PC_NAME>{pc_name}</PC_NAME>
                <IP_ADDRESS>{ip_address}</IP_ADDRESS>
                <TIME_STAMP>{time_stamp}</TIME_STAMP>
                """

                mxf_to_txt_path = part3_import_upload.change_extension_and_fill_content_if_txt(stem_file_path, "txt",
                                                                                               content_in_txt)
                if mxf_to_txt_path == False:
                    os.remove(stem_file_path)
                    continue
                #########################
                #### 인제스트 대상파일의 길이를 보고 10시간이 넘으면 빠꾸 시켜야 할듯 ;;

                ###################
                # config.command_txt_path: 파일 경로가 저장된 변수 (예: "C:/path/to/command.txt")
                file_path = config.command_txt_path
                content_to_write = f"{ingest_file_path},i,n"

                try:
                    mcdb_file_name = None
                    mcdb_file_full_path = None

                    with open(file_path, 'w', encoding='utf-8') as file:
                        file.write(content_to_write)
                    print(f"✅ 파일에 내용이 성공적으로 덮어쓰기 되었습니다(인풋): {file_path}")
                    status_text_var.set(f"{ingest_file_path}작업 중입니다.")
                    making_time = datetime.datetime.now()
                    time.sleep(7)

                    while True:
                        mcdb_file_name = os.path.basename(ingest_file_path) + " 48000.pek"
                        mcdb_file_full_path = config.find_files_with_phrase_in_targetfolder(config.nas_cache_path,
                                                                                            ".mcdb", mcdb_file_name)
                        print(f"찾은 mcdb 파일의 경로 입니다 {mcdb_file_full_path}")
                        if mcdb_file_full_path:
                            break
                        else:
                            print("5초 있다가 다시 찾아보겠습니다.")
                            time.sleep(5)


                except FileNotFoundError:
                    print(f"❌ 오류: 지정된 경로를 찾을 수 없습니다: {file_path}")
                except Exception as e:
                    print(f"❌ 파일을 쓰는 중 오류 발생: {e}")

                ### 프리미어에 파일 import 완료

                nas_cache_path = config.nas_cache_path
                nas_cache_path = os.path.join(nas_cache_path, "Peak Files")

                while True:

                    check_file_path_state = check_import_status(file_path, 'r')
                    if check_file_path_state:
                        print("watch_txt기입이 틀어졌음으로 나갑니다. (5분이 지나고 다른 PC가 작업하게 합니다.)")
                        break
                    else:
                        print("watch_txt기입은 정상입니다 - 진행합니다")

                    print("임포트 이후에 다 만들어짐을 확인하는 루프입니다.-2")

                    if is_file_silent(ingest_file_path):  ## 혹시 pek를 만들지 않는 무음인지 탐색
                        try:
                            file_path = config.command_txt_path
                            content_to_write = f"{ingest_file_path},r,n"
                            with open(file_path, 'w', encoding='utf-8') as file:
                                file.write(content_to_write)
                            print(f"✅ 파일에 내용이 성공적으로 덮어쓰기 되었습니다(아웃): {file_path}")
                            time.sleep(7)
                        except FileNotFoundError:
                            print(f"❌ 오류: 지정된 경로를 찾을 수 없습니다: {file_path}")
                        except Exception as e:
                            print(f"❌ 파일을 쓰는 중 오류 발생: {e}")

                        while True:
                            mcdb_file_name = os.path.basename(ingest_file_path)
                            mcdb_file_full_path = config.find_files_with_phrase_in_targetfolder(config.nas_cache_path,
                                                                                                ".mcdb", mcdb_file_name)
                            if mcdb_file_full_path:
                                break
                            else:
                                print("5초 있다가 다시 찾아보겠습니다.")
                                time.sleep(5)
                        ## pek 파일이 없는 무음이라 mcdb_file_path를 다시 잡습니다.

                        config.copy_file_force(nas_adobe_DB_cache_path, mcdb_file_full_path)
                        time.sleep(1)
                        config.move_file_force(backup_nas_adobe_DB_cache_path, mcdb_file_full_path)
                        print("무음이라 따로 작업하지 확장자 변경 후  나갑니다.")
                        print(f"{mxf_to_txt_path}의 확장자를 바꿉니다.(.finish)")
                        rename_file_extension(mxf_to_txt_path, ".finish")
                        print(f"확장자를 변경을 완료 했습니다")
                        print("15초 후에 나갑니다.")
                        time.sleep(15)
                        break

                    time.sleep(15)  ## 여기서 써치를 너무 빨리하는 경우가 생김
                    list_of_pek = config.search_cache_files_by_datetime(nas_cache_path, ingest_file_path, making_time)
                    time.sleep(15)  ## 여기서 써치를 너무 빨리하는 경우가 생김
                    list_of_pek = config.search_cache_files_by_datetime(nas_cache_path, ingest_file_path, making_time)
                    print(f"pek 파일 후보 리스트 입니다 {list_of_pek}")
                    if len(list_of_pek) == 0:
                        print('이미 어디선가 피크파일은 있고 복사나 위치를 변경한게 아닌가 싶습니다. 15초 후에 나갑니다.')
                        try:
                            file_path = config.command_txt_path
                            content_to_write = f"{ingest_file_path},r,n"
                            with open(file_path, 'w', encoding='utf-8') as file:
                                file.write(content_to_write)
                            print(f"✅ 파일에 내용이 성공적으로 덮어쓰기 되었습니다(아웃): {file_path}")
                            time.sleep(7)
                            config.copy_file_force(nas_adobe_DB_cache_path, mcdb_file_full_path)
                            time.sleep(1)
                            config.move_file_force(backup_nas_adobe_DB_cache_path, mcdb_file_full_path)
                            print("db 파일 옴기기 성공")
                        except FileNotFoundError:
                            print(f"❌ 오류: 지정된 경로를 찾을 수 없습니다: {file_path}")
                        except Exception as e:
                            print(f"❌ 파일을 쓰는 중 오류 발생: {e}")

                        print(f"{mxf_to_txt_path}의 확장자를 바꿉니다.(.finish)")
                        rename_file_extension(mxf_to_txt_path, ".finish")
                        print(f"확장자를 변경을 완료 했습니다")
                        time.sleep(15)
                        break

                    while True:
                        check = False
                        time.sleep(10)
                        print(f"피크파일 생성여부를 확인합니다. 현재 값 {check}")
                        check = part3_import_upload.check_make_finish_by_binary(list_of_pek)
                        print(f"피크파일 생성 결과입니다 {check}")
                        if check:
                            time.sleep(10)
                            print("작업을 완료했습니다 확장자를 바꾸고 나갑니다.")
                            try:
                                file_path = config.command_txt_path
                                content_to_write = f"{ingest_file_path},r,n"
                                with open(file_path, 'w', encoding='utf-8') as file:
                                    file.write(content_to_write)
                                print(f"✅ 파일에 내용이 성공적으로 덮어쓰기 되었습니다(아웃): {file_path}")
                                time.sleep(7)
                                config.copy_file_force(nas_adobe_DB_cache_path, mcdb_file_full_path)
                                time.sleep(1)
                                config.move_file_force(backup_nas_adobe_DB_cache_path, mcdb_file_full_path)
                                print("피크파일을 옴겼습니다")
                            except FileNotFoundError:
                                print(f"❌ 오류: 지정된 경로를 찾을 수 없습니다: {file_path}")
                            except Exception as e:
                                print(f"❌ 파일을 쓰는 중 오류 발생: {e}")

                            print(f"{mxf_to_txt_path}의 확장자를 바꿉니다.(.finish)")
                            rename_file_extension(mxf_to_txt_path, ".finish")
                            print(f"확장자를 변경을 완료 했습니다")
                            time.sleep(3)
                            break
                        else:
                            print("피크파일 생성을 기다립니다.")
                            time_stamp = datetime.datetime.now()
                            # 2. 시간을 문자열로 변환할 포맷을 정의합니다.
                            time_format = "%Y-%m-%d %H:%M:%S"
                            # 3. datetime 객체를 포맷에 맞는 문자열로 변환합니다. (strftime 사용)
                            time_stamp = time_stamp.strftime(time_format)
                            part3_import_upload.write_txt_tag_and_content(mxf_to_txt_path, "TIME_STAMP", time_stamp)
                            ## 타임스탬프 찍기
                            continue

                    break

                if stop_flag.wait(1):
                    break  # 취소 요청이 들어오면 루프 종료
            if stop_flag.wait(1):
                break  # 취소 요청이 들어오면 루프 종료
        except:
            if stop_flag.wait(1):
                break  # 취소 요청이 들어오면 루프 종료
            print("오류로 빠짐")
            time.sleep(5)

    print("작업 스레드 종료됨.")


def on_show():
    global root

    # [수정] 헬퍼 함수 호출 (핸들 목록을 반환)
    hwnds = get_premiere_hwnds()

    if hwnds:
        # 모든 핸들에 대해 조작을 수행합니다.
        for hwnd in hwnds:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # 가장 마지막으로 조작한 창을 활성화합니다. (혹은 가장 중요한 메인 창을 선택)
        win32gui.SetForegroundWindow(hwnds[-1])

        update_status(f"프리미어 프로 창 {len(hwnds)}개가 보이게 실행되었습니다.")
    else:
        update_status("프리미어 프로를 찾지 못함")


def on_hide():
    hwnds = get_premiere_hwnds()

    if hwnds:
        count = 0

        # 🚨 개선 1: 포커스 권한 우회 및 강화
        current_process_id = win32api.GetCurrentProcessId()

        # 1. AllowSetForegroundWindow 호출 (현재 프로세스에 포커스 권한 부여)
        ctypes.windll.user32.AllowSetForegroundWindow(current_process_id)

        # 2. 강제 활성화를 위해 창을 잠시 맨 위로 보냈다가 다시 해제
        # (이것이 SetForegroundWindow 실패 시 흔히 사용되는 우회 방법입니다)
        # 단, 첫 번째 핸들에만 적용합니다.
        try:
            target_hwnd = hwnds[0]
            win32gui.SetWindowPos(
                target_hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            # 즉시 다시 원래대로 (SetForegroundWindow가 작동할 수 있는 기반 마련)
            win32gui.SetWindowPos(
                target_hwnd,
                win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            time.sleep(0.05)  # 잠시 대기
        except Exception as e:
            # 포커스 권한 우회 시 실패해도 계속 진행
            print(f"경고: SetWindowPos를 통한 포커스 우회 실패: {e}")
            pass

        # 모든 핸들을 순회하며 작업을 수행합니다.
        for hwnd in hwnds:
            try:
                # 1. 창을 활성화(맨 앞으로 가져오기)
                # 권한 우회 로직이 실패할 수 있으므로 try/except 블록 안에 넣어 안정성을 확보합니다.
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)  # 포커스 이동 대기

                # 2. pyautogui를 사용하여 ESC 키 입력
                pyautogui.press('escape')
                print("✅ Escape 키 입력 완료.")
                time.sleep(0.1)  # 키 입력 처리 대기

                # 3. 창을 숨김 처리 (ESC 입력 후 숨김)
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                count += 1

            except Exception as e:
                if 'SetForegroundWindow' in str(e):
                    # SetForegroundWindow 실패 시 키 입력과 숨김을 건너뛰거나,
                    # 키 입력 없이 숨김만 시도할 수 있습니다.
                    print(f"경고: HWND {hwnd} 포커스 획득 실패 (액세스 거부). 키 입력은 건너뜝니다.")
                    # 키 입력 실패 시라도 숨김 자체는 시도할 수 있습니다.
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    count += 1
                else:
                    print(f"경고: 창 처리 중 기타 오류 발생: {e}")

        update_status(f"프리미어 프로 창 {count}개에 ESC 입력 후 숨김 처리되었습니다.")
    else:
        update_status("프리미어 프로를 찾지 못함")


def on_start():
    global btn_start
    global btn_cancel
    global status_text_var
    global running_thread
    global stop_flag
    global combo_pgm
    global combo_scan_day
    global day_before_scan
    #
    # warning_message = (
    #     """
    # 🚨 중요! Adobe 캐시 자동 삭제 설정을 확인해주세요 🚨
    #
    # 1.  <--설정 위치 확인-->
    #     프리미어 프로(Premiere Pro)에서 **
    #     [편집 Edit] > [환경 설정 Preferences ] > [미디어 캐시(Media Cache)]
    #     를 확인해주세요.
    #
    # 2.  <--삭제 주기 권장 사항-->
    #     자동 정리 옵션을 180일 로 설정해주세요.
    #
    # 3.  <--경고: 용량 제한 설정 금지!-->
    #     만약  **'23G'**와 같이 **용량 제한**으로  설정 되어 있다면,
    #     다른 PC가 만든 캐시를 불필요하게 삭제하여 공동 작업에 오류를 일으킬 수 있습니다.
    #     반드시 **기간 제한 (예: 180일)**으로 변경해야 합니다.
    # """
    # )
    #
    # # Tkinter 메시지 박스를 사용하면 코드가 가장 간결해집니다.
    # # title: 팝업창의 제목
    # # message: 팝업창에 표시될 내용
    # messagebox.showwarning(
    #     title="⚠️ 중요 안내: Premiere Pro 작동 조건",
    #     message=warning_message
    # )
    # """ '시작' 버튼을 눌렀을 때 실행될 함수 """

    config.pgm = config.parse_pgm_range(config.pgm)
    random.shuffle(config.pgm)
    ### 일단 여기 넣기
    print(f"{config.pgm}")

    day_before_scan = config.scan_day

    print("시작 버튼 클릭")
    btn_start.config(state="disabled")
    btn_cancel.config(state="normal")
    combo_pgm.config(state="disabled")
    combo_scan_day.config(state="disabled")
    # (이곳에 실제 '시작' 로직을 추가할 수 있습니다.)
    time.sleep(2)
    try:
        # 경로의 파일을 실행합니다.

        config.launch_premiere_from_config()
        time.sleep(10)

    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다: {config.startup_proj_path}")
    except Exception as e:
        print(f"파일 실행 중 오류 발생: {e}")

    on_hide()
    if status_text_var:
        status_text_var.set("✅ 작업중입니다...")

    # 3. 작업 스레드 시작
    stop_flag.clear()  # 확실하게 취소 플래그 초기화
    running_thread = threading.Thread(target=worker_loop)
    running_thread.daemon = True  # 메인 프로그램 종료 시 스레드도 종료되도록 설정
    running_thread.start()

    # 예시: 상태 메시지를 실제 작업 파일 경로로 업데이트
    dummy_file_path = "와치 작업중입니다."
    update_status(f"처리 중... {dummy_file_path}")

    # (파일 처리가 오래 걸린다면 이곳에서 스레드를 시작하는 것이 좋습니다.)


def on_cancel():
    global btn_start
    global btn_cancel
    global status_text_var
    global running_thread
    global stop_flag
    global combo_pgm
    global combo_scan_day
    """ '취소' 버튼을 눌렀을 때 실행될 함수 """
    print("취소 버튼 클릭")

    # 1. 취소 요청 플래그 설정
    if running_thread and running_thread.is_alive():
        print("작업 스레드에 종료 요청을 보냅니다...")
        stop_flag.set()  # 스레드 종료 요청
        # (선택 사항) 스레드가 완전히 종료될 때까지 잠시 대기
        # running_thread.join(timeout=1)

    btn_start.config(state="normal")
    btn_cancel.config(state="disabled")
    combo_pgm.config(state="normal")
    combo_scan_day.config(state="normal")

    if status_text_var:
        status_text_var.set("✅ 하던 작업까지 진행하고 종료합니다. 자동으로 창이 닫힙니다..")

    # (이곳에 '취소' 로직을 추가할 수 있습니다. 예: 실행 중인 스레드 중지)
    update_status("하던 작업까지 진행하고 종료합니다. 자동으로 창이 닫힙니다.")
    on_show()
    time.sleep(5)
    hwnd = get_premiere_hwnds()
    for hwnd in hwnd:
        if terminate_program_by_hwnd(hwnd):
            print("프로그램 종료 작업 성공.")
            sys.exit(0)
        else:
            print("프로그램 종료 작업 실패.")


def update_status(message):
    """ 하단 상태 메시지를 업데이트하는 헬퍼 함수 """
    # current_file_path (StringVar)의 값을 변경하면
    # 이 변수와 연결된 Label(lbl_status_dynamic)의 텍스트가 자동으로 바뀝니다.
    global current_file_path
    current_file_path.set(message)


def update_status_from_main(message):
    global status_text_var
    if status_text_var:
        status_text_var.set(f"▶ {message}")


# --- gui생성 전 사전작업 (Main Window) ---


def ui():
    global current_file_path
    global root
    global status_text_var
    global btn_start
    global btn_cancel
    global combo_pgm
    global combo_scan_day

    # --- GUI 설정 (Main Window) ---
    # 1. 메인 윈도우 생성
    root = tk.Tk()
    status_text_var = tk.StringVar(root)
    status_text_var.set("프로그램 시작 준비 중...")  # 초기 텍스트 설정
    root.title("피크파일 도우미")  # 윈도우 상단 표시줄 제목
    root.geometry("750x700")  # 윈도우 초기 크기
    root.configure(bg="#f0f0f0")  # 윈도우 전체 배경색 (밝은 회색)
    root.attributes("-topmost", True)  ## 항상 맨 위에 위치
    # --- 2. 텍스트 영역 (제목/설명) ---
    # (상단 버튼이 사라지고 이 부분이 최상단이 됨)
    frame_text = tk.Frame(root, pady=10, bg=root.cget('bg'))
    frame_text.pack(fill=tk.X, padx=25, pady=(10, 0))  # 가로로 채우고 좌우/상단 여백

    # 제목 (파란색, 굵게)
    title_font = tkFont.Font(family="Malgun Gothic", size=24, weight="bold")
    lbl_title = tk.Label(frame_text, text="피크파일 생성 도우미", font=title_font, fg="#0052cc", bg=root.cget('bg'))
    lbl_title.pack()

    # 설명 (검은색)
    desc_font = tkFont.Font(family="Malgun Gothic", size=14)
    lbl_desc = tk.Label(frame_text,
                        text="\n\n<선택 PGM>의\n01_ingest 부터 09_Export의 폴더를 와치하면서 피크파일을 생성합니다.\n\n 준비 시간이 30초 가량 소요됩니다.\n\n 프리미어 버그로 10시간 이상 동영상은 피크를 만들지 않습니다.\n\n Q&A LSJ(319077) ",
                        font=desc_font, fg="black", bg=root.cget('bg'))
    lbl_desc.pack()  # 위쪽(5), 아래쪽(0) 여백

    # --- 3. 메인 버튼 (시작/취소) ---
    frame_controls = tk.Frame(root, pady=20, bg=root.cget('bg'))
    frame_controls.pack()  # 중앙에 배치

    # '시작' 버튼 (초록색 계열, 폰트 굵게)
    start_font = tkFont.Font(family="Malgun Gothic", size=10, weight="bold")
    btn_start = tk.Button(frame_controls, text="시작", width=12, height=2, command=on_start,
                          bg="#4CAF50", fg="white", font=start_font, relief=tk.FLAT, borderwidth=0)
    # [수정] 아래 잘못된 코드를 삭제하고, 시작/취소 버튼 pack 코드를 복원합니다.
    # lbl_desc.pack(anchor="w", pady=(5, 0))  <-- 이 줄이 잘못되었습니다.
    btn_start.pack(side=tk.LEFT, padx=10)

    # [추가] 시작 버튼과 취소 버튼 사이에 텍스트 레이블 추가
    # (start_font를 재사용하거나 새 폰트를 정의할 수 있습니다.)
    lbl_between = tk.Label(frame_controls, text=" | ", font=start_font, bg=root.cget('bg'), fg="#888888")
    lbl_between.pack(side=tk.LEFT, padx=0)  # 버튼 사이에 0의 여백으로 붙임

    # '취소' 버튼 (빨간색 계열, 폰트 굵게)
    btn_cancel = tk.Button(frame_controls, text="취소", width=12, height=2, command=on_cancel,
                           bg="#f44336", fg="white", font=start_font, relief=tk.FLAT, borderwidth=0)
    btn_cancel.pack(side=tk.LEFT, padx=10)
    btn_cancel.config(state="disabled")
    # [추가] 두 버튼 섹션 사이에 들어갈 새 텍스트 레이블
    # (새 폰트를 정의하거나, desc_font 등을 재사용할 수 있습니다.)
    interim_font = tkFont.Font(family="Malgun Gothic", size=20)
    lbl_interim = tk.Label(root,
                           textvariable=status_text_var,
                           font=interim_font,
                           bg=root.cget('bg'),
                           fg="#FF0000")
    # pady=(10, 0)을 줘서 위쪽(시작/취소 버튼)과는 10만큼,
    # 아래쪽(보이기/숨기기)과는 0만큼 떨어지게 합니다.
    lbl_interim.pack(pady=(10, 0))

    # --- [추가됨] 2.5 PGM 선택 드롭다운 영역 ---
    frame_input = tk.Frame(root, pady=5, bg=root.cget('bg'))
    frame_input.pack()

    # 라벨
    lbl_pgm = tk.Label(frame_input, text="PGM 선택 : ", font=("Malgun Gothic", 12, "bold"), bg=root.cget('bg'))
    lbl_pgm.pack(side=tk.LEFT, padx=5)

    # 드롭다운 값 생성 (PGM00 ~ PGM99)
    pgm_values = ["전구간", "PGM00 - PGM09", "PGM10 - PGM19", "PGM20 - PGM29", "PGM30 - PGM39", "PGM40 - PGM49",
                  "PGM50 - PGM59", "PGM60 - PGM69", "PGM70 - PGM79", "PGM80 - PGM89", "PGM90 - PGM99"]
    # 변수 바인딩
    pgm_var = tk.StringVar()
    pgm_var.set("전구간")  # config에 값이 있으면 가져오고 없으면 PGM01

    # 콤보박스 생성 (읽기 전용으로 설정하여 직접 타이핑 방지)
    combo_pgm = ttk.Combobox(frame_input, textvariable=pgm_var, values=pgm_values, state="readonly", width=18,
                             font=("Malgun Gothic", 11))
    combo_pgm.pack(side=tk.LEFT, padx=5)

    # [중요] 드롭다운 변경 시 config.pgm 업데이트 함수
    def on_pgm_changed(event):
        selected_value = pgm_var.get()
        config.pgm = selected_value
        print(f"[설정 변경] Target PGM: {config.pgm}")  # 확인용 로그

        # 상태 메시지 업데이트 (선택사항)
        status_text_var.set(f"{config.pgm} 작업 준비 완료")

    # 이벤트 바인딩 (값이 선택될 때마다 함수 실행)
    combo_pgm.bind("<<ComboboxSelected>>", on_pgm_changed)

    # --- [추가됨] 2.5 PGM 선택 드롭다운 영역 ---
    frame2_input = tk.Frame(root, pady=5, bg=root.cget('bg'))
    frame2_input.pack()

    # 라벨
    lbl_scan_day = tk.Label(frame2_input, text="인제스트 된지 N일 전 파일부터 만들겠습니다. : ", font=("Malgun Gothic", 12, "bold"),
                            bg=root.cget('bg'))
    lbl_scan_day.pack(side=tk.LEFT, padx=5)

    # 드롭다운 값 생성 (PGM00 ~ PGM99)
    scan_day_values = [90, 60, 30, 10, 5, 3, 1]
    scan_day_var = tk.StringVar()
    scan_day_var.set(3)  # config에 값이 있으면 가져오고 없으면 1

    # 콤보박스 생성 (읽기 전용으로 설정하여 직접 타이핑 방지)
    combo_scan_day = ttk.Combobox(frame2_input, textvariable=scan_day_var, values=scan_day_values, state="readonly",
                                  width=18,
                                  font=("Malgun Gothic", 11))
    combo_scan_day.pack(side=tk.LEFT, padx=5)

    # [중요] 드롭다운 변경 시 config.pgm 업데이트 함수
    def on_scan_day_changed(event):
        selected_value = scan_day_var.get()
        config.scan_day = selected_value
        print(f"[설정 변경] 스캔데이: {config.scan_day}")  # 확인용 로그

        # 상태 메시지 업데이트 (선택사항)
        status_text_var.set(f"{config.scan_day}일 이내 파일을 생성합니다.")

    # 이벤트 바인딩 (값이 선택될 때마다 함수 실행)
    combo_scan_day.bind("<<ComboboxSelected>>", on_scan_day_changed)

    # --- 3. 하단 토글 버튼 (보이기/숨기기) ---
    # (이전 코드에서는 섹션 3이었으나, 4로 정정합니다)

    # [수정] 아래 2줄 정의(definition) 코드 추가
    frame_toggle_bottom = tk.Frame(root, pady=10, bg=root.cget('bg'))
    frame_toggle_bottom.pack(anchor='e', padx=25)  # 오른쪽 정렬 (anchor='e')
    # [수정] 아래 1줄 폰트 정의(definition) 코드 추가
    toggle_title_font = tkFont.Font(family="Malgun Gothic", size=10, weight="bold")

    lbl_toggle_title = tk.Label(frame_toggle_bottom, text="프리미어프로 보이기/숨기기", font=toggle_title_font, fg="black",
                                bg=root.cget('bg'))
    # [수정] anchor='w' (왼쪽) -> 'e' (오른쪽)로 변경
    lbl_toggle_title.pack(anchor="e", pady=(0, 5))  # 버튼 위에 5만큼 아래 여백

    # '보이기'/'숨기기' 버튼을 담을 내부 프레임
    frame_toggle_buttons = tk.Frame(frame_toggle_bottom, bg=root.cget('bg'))
    # [수정] anchor='w' (왼쪽) -> 'e' (오른쪽)로 변경
    frame_toggle_buttons.pack(anchor="e")

    btn_show = tk.Button(frame_toggle_buttons, text="보이기", width=10, command=on_show)
    btn_show.pack(side=tk.LEFT, padx=(0, 5))  # 왼쪽 여백 0, 오른쪽 여백 5

    btn_hide = tk.Button(frame_toggle_buttons, text="숨기기", width=10, command=on_hide)
    btn_hide.pack(side=tk.LEFT, padx=5)

    # --- 5. 하단 상태 표시줄 ---
    # (side=BOTTOM을 사용해 윈도우 하단에 고정)

    # StringVar: 레이블의 텍스트를 동적으로 변경하기 위한 특수 변수
    current_file_path = tk.StringVar()
    current_file_path.set("대기 중...")  # 초기 상태 메시지

    # 상태 표시줄 프레임 (약간 어두운 배경)
    frame_status = tk.Frame(root, pady=5, padx=10, bg="#e0e0e0", relief=tk.SUNKEN, bd=1)
    frame_status.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)  # 하단에 고정하고 가로로 채우기

    # "현재 작업중인 파일 :" 고정 텍스트
    lbl_status_fixed = tk.Label(frame_status, text="현재 작업중인 파일 : ", font=("Malgun Gothic", 9, "bold"),
                                bg=frame_status.cget('bg'))
    lbl_status_fixed.pack(side=tk.LEFT)

    # 동적으로 변경될 파일 경로 레이블
    # (textvariable가 current_file_path로 설정되어 있어, 변수 값이 바뀌면 레이블 텍스트도 바뀜)
    lbl_status_dynamic = tk.Label(frame_status, textvariable=current_file_path, font=("Malgun Gothic", 9),
                                  bg=frame_status.cget('bg'), fg="#333333")
    lbl_status_dynamic.pack(side=tk.LEFT, fill=tk.X, expand=True)  # 남은 공간을 채우도록 설정

    def disable_close_event():
        hwnds = get_premiere_hwnds()
        if not hwnds:
            sys.exit(0)
        status_text_var.set(f"취소 버튼으로만 닫을 수 있습니다.")

    # [추가] 윈도우 닫기 프로토콜을 위 함수로 연결
    root.protocol("WM_DELETE_WINDOW", disable_close_event)

    root.mainloop()






