import re
import os
import subprocess
import sys  # <--- 추가 (sys.executable 사용)
import shutil  # <--- 추가 (shutil.rmtree 사용)
from pathlib import Path  # <--- 추가 (Path 객체 사용)
import time  # <--- 추가 (time.sleep 사용)
import win32con  # <--- 추가 (Windows 상수 사용)
import win32gui  # <--- 추가 (Windows GUI 제어)
import traceback  # <--- 추가 (traceback.print_exc 사용)
from datetime import datetime, timedelta

import socket




############################### 설정변수
watch_folder_path = None
command_txt_path = ""
startup_jsx_path = ""
startup_proj_path = ""
last_pek_file_path = [] ### 피크파일을 물고있어서 한번 넣어다 빼줘야 하네;; 최근 파일의 pek를 물고 있습니다.
for_peak_out_file_list = []

premiere_path = r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe"
### 24버전이면 바꿔줘야함
nas_cache_path = r"\\npsmain.mbcnps.com\DEV_ROOT\Adobe_Cache"
pgm="전구간"
scan_day = 3



################################### 설정 변수 끝

def parse_pgm_range(selection_text):
    """
    드롭다운 선택 텍스트를 분석하여 PGM 리스트를 반환합니다.
    - "전구간" -> PGM00 ~ PGM99
    - "PGM00 - PGM09" -> PGM00 ~ PGM09
    """
    if selection_text == "전구간":
        return [f"PGM{i:02d}" for i in range(100)]

    try:
        # "PGM00 - PGM09" 형태 파싱
        if " - " in selection_text:
            start_part, end_part = selection_text.split(" - ")
            # 숫자 부분만 추출 (PGM 제거)
            start_num = int(start_part.replace("PGM", ""))
            end_num = int(end_part.replace("PGM", ""))

            # range의 끝값은 포함되지 않으므로 +1
            return [f"PGM{i:02d}" for i in range(start_num, end_num + 1)]

        # 혹시 "PGM01" 처럼 단일 값이 들어올 경우
        return [selection_text]

    except Exception as e:
        print(f"[Error] PGM 파싱 오류: {e}")
        return []

def create_folder_in_exe_dir(folder_name: str, clear_if_exists: bool = False) -> str | None:
    """
    스크립트(또는 .exe)가 실행된 위치에
    지정한 'folder_name'으로 폴더를 생성합니다.

    Args:
        folder_name (str): 생성할 폴더의 이름. (예: "Logs", "Output")
        clear_if_exists (bool):
            True - 폴더가 이미 존재하면, 내용물 전체를 삭제하고 새로 만듭니다.
            False - 폴더가 이미 존재하면, 아무 작업도 하지 않습니다. (기본값)
                    존재하지 않으면 새로 만듭니다.

    Returns:
        str | None: 생성된 폴더의 '전체 경로 문자열(full path)', 또는 오류 시 None
    """

    try:
        # 1. 스크립트(실행 파일)가 위치한 기본 디렉터리
        start_dir = Path(sys.executable).parent

        # 2. 생성할 타겟 폴더의 전체 경로 (Path 객체)
        target_folder = start_dir / folder_name

        print(f"--- 폴더 생성 작업 ---")
        print(f"기준 디렉터리: {start_dir}")
        print(f"대상 폴더 이름: {folder_name}")
        print(f"정리 옵션(clear): {clear_if_exists}")

        # 3. 폴더 존재 여부 확인
        if target_folder.exists():

            # 4. [True] 옵션: 삭제하고 새로 만들기
            if clear_if_exists:
                print(f"  [정보] '{folder_name}' 폴더가 이미 존재합니다. 내용을 삭제하고 다시 만듭니다.")
                try:
                    shutil.rmtree(target_folder)
                    target_folder.mkdir()
                    print(f"  [성공] 폴더 정리 및 재생성 완료: {target_folder}")
                except OSError as e:
                    print(f"  [오류] 폴더 삭제/재생성 실패: {e}")
                    return None

            # 5. [False] 옵션: (기본값) 존재하면 내버려 두기
            else:
                print(f"  [정보] '{folder_name}' 폴더가 이미 존재합니다. (작업 건너뜀)")

        # 6. 폴더가 존재하지 않는 경우: 새로 만들기
        else:
            print(f"  [정보] '{folder_name}' 폴더를 새로 생성합니다.")
            try:
                # parents=True : 중간 경로가 없어도 생성 (안전장치)
                target_folder.mkdir(parents=True, exist_ok=True)
                print(f"  [성공] 새 폴더 생성 완료: {target_folder}")
            except OSError as e:
                print(f"  [오류] 폴더 생성 실패: {e}")
                return None

        # 7. [수정됨] 성공 시 '전체 경로 문자열' 반환
        # .resolve()로 절대 경로를 확실히 한 후 str()로 변환
        return str(target_folder.resolve())

    except Exception as e:
        print(f"[심각한 오류] 스크립트 경로 확인 중 오류: {e}")
        return None


def find_file_in_executable_subdirs(filename_to_find):
    """
    sys.executable의 위치에서 시작하여 모든 하위 폴더를 재귀적으로 탐색하고,
    지정된 파일 이름과 일치하는 첫 번째 파일의 전체 경로를 반환합니다.

    Args:
        filename_to_find (str): 찾고자 하는 파일 이름 (예: "start.prproj")

    Returns:
        str: 찾은 파일의 전체 경로. 파일을 찾지 못하면 None을 반환합니다.
    """
    # sys.executable의 디렉토리를 탐색 시작 경로로 설정합니다.
    # sys.executable은 Python 인터프리터의 전체 경로를 포함합니다.
    start_dir = os.path.dirname(sys.executable)
    print(f"탐색 시작 경로: {start_dir}")

    # os.walk를 사용하여 시작 디렉토리와 모든 하위 디렉토리를 재귀적으로 탐색합니다.
    for root, _, files in os.walk(start_dir):
        # 현재 디렉토리(root)에 찾고자 하는 파일이 있는지 확인합니다.
        if filename_to_find in files:
            print(files)
            # 파일이 발견되면, os.path.join을 사용하여 전체 경로를 구성하고 반환합니다.
            full_path = os.path.join(root, filename_to_find)
            return full_path

    # 모든 디렉토리를 탐색했으나 파일을 찾지 못한 경우
    return None

def find_files_in_documents_pathlib(filename_to_find):
    """
    pathlib를 사용하여 '문서' 폴더에서 파일을 재귀적으로 찾습니다.
    """
    documents_path = Path.home() / "Documents"
    found_files_list = []

    if not documents_path.exists():
        print(f"오류: '문서' 폴더를 찾을 수 없습니다. (경로: {documents_path})")
        return found_files_list

    # **/*.py 처럼 glob 패턴을 사용하지 않고 정확한 파일 이름만 검색할 경우:
    # rglob(filename_to_find)는 해당 이름과 정확히 일치하는 파일을 재귀적으로 찾습니다.
    # 대소문자 구분을 무시하고 싶다면, 직접 리스트를 필터링해야 합니다.

    # pathlib.rglob(패턴)을 사용하여 파일을 찾습니다.
    # '**'는 모든 하위 디렉토리를 의미합니다.
    # filename_to_find가 "Adobe Premiere Pro Prefs"라면,
    # documents_path.rglob("*/Adobe Premiere Pro Prefs")를 실행합니다.

    # 찾는 이름과 정확히 일치하는 모든 경로를 리스트에 담습니다.
    for path_obj in documents_path.rglob(filename_to_find):
        if path_obj.is_file():
            found_files_list.append(str(path_obj))

    return found_files_list




def update_jsx_paths(jsx_file_path, new_watch_folder):
    """
    기존 .jsx 파일의 경로 변수 1개(WATCH_FOLDER_PATH)를 찾아 새 경로로 교체합니다.
    (참고: 주석과 달리 실제 코드는 1개의 변수만 교체하도록 되어 있었습니다.)

    Args:
        jsx_file_path (str): 수정할 .jsx 파일의 경로
        new_watch_folder (str): 새로운 WATCH_FOLDER_PATH 경로
    """

    # 1. 원본 .jsx 파일 읽기 (UTF-8)
    try:
        with open(jsx_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다: {jsx_file_path}")
        return
    except Exception as e:
        print(f"오류: 파일을 읽는 중 문제가 발생했습니다: {e}")
        return

    # 2. Python 경로(예: "C:\path")를 JS 문자열("C:\\path")로 변환
    js_watch_folder = new_watch_folder.replace('\\', '\\\\')

    # 3. 교체할 문자열 정의
    # (수정) 정규식을 개선하여 var/let/const 및 기존 따옴표(' 또는 ")를 모두 처리하고,
    #       라인의 나머지 부분(주석 등)을 보존하도록 함.
    replacement_map = {
        # (var/let/const WATCH_FOLDER_PATH =) ("기존경로") (;)
        re.compile(r'((?:var|let|const)\s+WATCH_FOLDER_PATH\s*=\s*)["\'][^"\']*["\'](\s*;?)'):
            lambda m: f'{m.group(1)}"{js_watch_folder}"{m.group(2) or ";"}'
    }

    # 만약 3개의 변수를 수정해야 했다면, replacement_map은 이런 모습이었을 것입니다:
    # replacement_map = {
    #     re.compile(r'((?:var|let|const)\s+WATCH_FOLDER_PATH\s*=\s*)["\'][^"\']*["\'](\s*;?)'):
    #         lambda m: f'{m.group(1)}"{js_watch_folder}"{m.group(2) or ";"}',
    #     re.compile(r'((?:var|let|const)\s+OTHER_PATH_1\s*=\s*)["\'][^"\']*["\'](\s*;?)'):
    #         lambda m: f'{m.group(1)}"{js_other_path_1}"{m.group(2) or ";"}',
    #     re.compile(r'((?:var|let|const)\s+OTHER_PATH_2\s*=\s*)["\'][^"\']*["\'](\s*;?)'):
    #         lambda m: f'{m.group(1)}"{js_other_path_2}"{m.group(2) or ";"}',
    # }
    # (이 경우 js_other_path_1, js_other_path_2 변수도 인자로 받아와야 합니다.)

    modified_content = content
    found_count = 0

    # 4. 정규식을 사용해 각 변수 라인 교체
    for pattern, replacement in replacement_map.items():
        modified_content, count = pattern.subn(replacement, modified_content)
        if count > 0:
            found_count += count  # 한 변수가 여러 번 나올 수도 있으므로 count를 더함
        else:
            # (수정) 어떤 변수를 못찾았는지 간단히 경고
            if "WATCH_FOLDER_PATH" in pattern.pattern:
                print(f"경고: WATCH_FOLDER_PATH 변수를 파일에서 찾지 못했습니다.")
            # 다른 변수들에 대한 경고도 여기에 추가할 수 있습니다.

    if found_count == 0:
        print("오류: 파일에서 교체할 변수를 하나도 찾지 못했습니다. 파일 내용을 확인해주세요.")
        return

    # 5. 수정된 내용으로 원본 파일 덮어쓰기 (UTF-8)
    try:
        with open(jsx_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"성공: '{jsx_file_path}' 파일의 경로 변수 {found_count}개가 업데이트되었습니다.")
    except Exception as e:
        print(f"오류: 파일을 저장하는 중 문제가 발생했습니다: {e}")



def launch_premiere_from_config():
    """
    config.py의 경로로 프리미어를 '보통 크기'로 실행한 뒤,
    창을 찾아서 '숨김(HIDE)' 상태로 만듭니다.
    """

    try:
        # 1. config 모듈에서 경로 변수를 가져옵니다.
        premiere_exe_path = premiere_path
        project_path = startup_proj_path
    except AttributeError as e:
        print(f"❌ 오류: config.py 파일에 필요한 변수가 없습니다. ({e})")
        return

    # 2. 작업 폴더(cwd) 설정
    premiere_install_dir = os.path.dirname(premiere_exe_path)

    try:
        # 3. 경로 유효성 검사 (생략)
        if not (os.path.exists(premiere_exe_path) and os.path.exists(project_path)):
            print("❌ 오류: 프리미어 또는 프로젝트 경로가 잘못되었습니다.")
            return

        # --- 4. 1단계: "보통 크기"로 실행 ---
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = win32con.SW_SHOWNORMAL  # "보통" 크기로 실행

        print(f"▶ 창 상태 강제: SW_SHOWNORMAL (보통 크기)로 실행...")

        # 5. Popen으로 프리미어 실행
        subprocess.Popen(
            [premiere_exe_path, project_path],
            cwd=premiere_install_dir,
            startupinfo=startupinfo
        )
        print(f"✅ 프리미어 프로 실행 완료.")

        # --- 6. 2단계: "찾아서 숨기기" ---

        # 프리미어 창이 뜨고 제목이 "Adobe Premiere Pro"가 될 때까지 기다림
        # (PC/프로젝트 로딩 속도에 따라 이 시간 조절이 필요할 수 있습니다)
        wait_time = 15
        print(f"... 프리미어 창을 찾기 위해 {wait_time}초 대기합니다 ...")
        time.sleep(wait_time)

        print("... 'Adobe Premiere Pro' 창 검색 중 ...")
        hwnd = None

        # 콜백 함수: 모든 창을 검사하며 제목에 "Adobe Premiere Pro"가 있는지 확인
        def find_window_callback(hwnd_cb, extra):
            window_title = win32gui.GetWindowText(hwnd_cb)
            if "Adobe Premiere Pro" in window_title and win32gui.IsWindowVisible(hwnd_cb):
                nonlocal hwnd
                hwnd = hwnd_cb
                return False  # 찾았으니 중지
            return True  # 계속 검색

        try:
            win32gui.EnumWindows(find_window_callback, None)
        except Exception as e:
            # EnumWindows는 콜백이 False를 반환하면 "No error message" 예외를 낼 수 있음
            if "No error message" not in str(e):
                print(f"❌ 창 검색 중 예외: {e}")

        # 창을 찾아서 숨김
        if hwnd:
            print(f"👍 프리미어 창(HWND: {hwnd})을 찾았습니다.")
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)  # ★★★ 창 숨기기
            print("✅ 창을 숨겼습니다. (SW_HIDE)")
        else:
            print(f"❌ {wait_time}초 내에 'Adobe Premiere Pro' 창을 찾지 못했습니다.")

    except Exception as e:
        print(f"❌ 오류: 프리미어 프로 실행 중 알 수 없는 문제 발생: {e}")
        import traceback
        traceback.print_exc()




def cleanup_empty_folders(target_folder: str):
    """
    주어진 폴더를 하위부터(bottom-up) 재귀적으로 탐색하여,
    내용물이 없는 빈 폴더를 모두 삭제합니다.

    Args:
        target_folder (str): 빈 폴더를 정리할 디렉터리 경로.
    """

    target_p = Path(target_folder)

    print(f"--- 빈 폴더 정리 시작 ---")
    print(f"대상 경로: {target_p}")

    # 대상 폴더가 없으면 메시지 출력 후 종료
    if not target_p.exists():
        print(f"  [정보] 대상 폴더가 존재하지 않아 정리할 수 없습니다.")
        return

    # topdown=False : 하위 폴더부터(bottom-up) 순회 (빈 폴더를 연쇄적으로 제거하기 위함)
    for root, dirs, files in os.walk(target_p, topdown=False):
        current_dir = Path(root)

        # 현재 폴더(root)가 비어있는지 확인
        # (os.listdir()은 '.'이나 '..'을 제외한 실제 파일/폴더 목록을 반환)
        try:
            if not os.listdir(current_dir):
                # 자기 자신(target_p)은 삭제하지 않도록 방지
                if current_dir != target_p:
                    print(f"  [삭제] 빈 폴더 제거: {current_dir}")
                    os.rmdir(current_dir)
        except OSError as e:
            # 권한 문제 등으로 폴더 삭제 실패 시
            print(f"  [오류] 폴더 삭제 실패 {current_dir}: {e}")

    print(f"--- 빈 폴더 정리 완료 ---")




def update_cache_path(CACHE_FOLDER_PATH,NEW_DB_PATH,VERSION ="25.0"):
    # 📌 2. CMD 창을 숨기기 위한 플래그
    # SW_HIDE: 창을 숨깁니다.
    # CREATE_NO_WINDOW: 창을 만들지 않습니다.
    if os.name == 'nt':  # 운영체제가 Windows일 때만 적용
        # 0x08000000은 subprocess.CREATE_NO_WINDOW에 해당합니다.
        # 윈도우 환경이 아니면 에러가 날 수 있으므로 os.name으로 체크합니다.
        HIDE_WINDOW_FLAG = 0x08000000
    else:
        HIDE_WINDOW_FLAG = 0

    # 📌 3. 명령어 템플릿 정의 (경로 변수를 f-string으로 삽입)
    KEY_PATH = f"HKEY_CURRENT_USER\\Software\\Adobe\\Common {VERSION}\\Media Cache"

    commands = [
        # DatabasePath 설정
        f'reg add "{KEY_PATH}" /v "DatabasePath" /t REG_SZ /d "{NEW_DB_PATH}" /f',
        # FolderPath 설정
        f'reg add "{KEY_PATH}" /v "FolderPath" /t REG_SZ /d "{CACHE_FOLDER_PATH}" /f'
    ]

    print("--- Adobe Media Cache 경로 변경 시작 ---")

    success = None
    # 📌 4. 각 명령어를 순서대로 실행
    for cmd in commands:
        # 명령어의 값 이름 추출 (예: "DatabasePath")
        value_name = cmd.split('/v')[1].split('/t')[0].strip().strip('"')

        try:
            # subprocess.run 실행 시 creationflags를 추가하여 창 숨김
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                capture_output=True,
                encoding='cp949',
                creationflags=HIDE_WINDOW_FLAG  # **CMD 창 숨김 설정**
            )
            success = True
            print(f'✅ 명령어 성공 요청하신 경로로 변경되었습니다')

        except subprocess.CalledProcessError as e:
            print(f"❌ 명령어 실패 ({value_name})")
            print(f"오류 코드: {e.returncode}")
            # CMD 창은 숨겨졌지만, 에러 메시지는 캡처하여 출력
            print(f"표준 에러: {e.stderr}")
            success = False
            break

    print("--- Adobe Media Cache 경로 변경 완료 ---")
    return success


# NEW_DB_PATH = "C:\\Adobe_Cache"  # DatabasePath에 사용할 경로
# CACHE_FOLDER_PATH = "C:\\Adobe_Cache"  # FolderPath에 사용할 경로
#
# update_cache_path(CACHE_FOLDER_PATH,NEW_DB_PATH)


def search_cache_files_by_datetime(document_root: str, source_filepath: str, target_time_ref: datetime) -> list[
    str]:
    """
    원본 파일 경로를 기반으로 캐시 파일을 검색하고, 입력된 datetime 객체 시간의
    ±2분 이내에 생성된 파일만 필터링하여 반환합니다. (datetime 객체 사용)

    :param document_root: 탐색을 시작할 최상위 폴더 경로
    :param source_filepath: 원본 미디어 파일의 전체 경로
    :param target_time_ref: 기준 시간 (datetime.datetime 객체)
    :return: 시간 조건에 맞는 캐시 파일의 전체 경로 리스트 (List[str])
    """

    # 1. 원본 파일 이름 및 목표 캐시 파일 이름 생성
    source_full_name = os.path.basename(source_filepath)
    target_cache_filename = f"{source_full_name} 48000.pek"

    # 2. 오늘과 어제의 날짜 폴더 이름 계산 (YYYY-MM-DD 형식)
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    today_folder = now.strftime('%Y-%m-%d')
    yesterday_folder = yesterday.strftime('%Y-%m-%d')

    # 3. 탐색할 폴더 경로 리스트 생성
    search_dirs = [
        os.path.join(document_root, today_folder),
        os.path.join(document_root, yesterday_folder)
    ]

    found_files = []

    print(f"🔎 검색 대상 폴더: {today_folder}, {yesterday_folder}")
    print(f"⏱️ 기준 시간: {target_time_ref.strftime('%H:%M:%S')} (± 2분 범위 검색)")

    # 4. 날짜 폴더 순회 및 시간 필터링
    for base_dir in search_dirs:

        if os.path.isdir(base_dir):

            # 현재 탐색 중인 폴더의 날짜 부분과 입력된 시간을 조합하여 기준 datetime 생성
            try:
                date_str = os.path.basename(base_dir)

                # 입력된 datetime 객체의 시/분/초를 현재 탐색 중인 날짜에 적용
                reference_datetime = datetime(
                    year=int(date_str.split('-')[0]),
                    month=int(date_str.split('-')[1]),
                    day=int(date_str.split('-')[2]),
                    hour=target_time_ref.hour,
                    minute=target_time_ref.minute,
                    second=target_time_ref.second
                )

                # 허용 시간 범위 계산 (기준 시간 ± 2분)
                time_min = reference_datetime - timedelta(minutes=2)
                time_max = reference_datetime + timedelta(minutes=2)

            except Exception:
                continue

            for dirpath, dirnames, filenames in os.walk(base_dir):
                if target_cache_filename in filenames:
                    full_path = os.path.join(dirpath, target_cache_filename)

                    # 5. 파일 생성 시간(ctime) 확인 및 필터링
                    file_ctime_timestamp = os.path.getctime(full_path)
                    file_ctime = datetime.fromtimestamp(file_ctime_timestamp)

                    if time_min <= file_ctime <= time_max:
                        found_files.append(full_path)
                        print(
                            f"✅ 조건 만족: {os.path.basename(full_path)} (생성 시간: {file_ctime.strftime('%Y-%m-%d %H:%M:%S')})")

    return found_files


def get_pc_info():
    """
    현재 PC의 이름(Hostname)과 로컬 IP 주소를 반환합니다.

    Returns:
        tuple: (pc_name, ip_address) 형태의 튜플
    """
    try:
        # PC 이름(Hostname) 가져오기
        pc_name = socket.gethostname()

        # 호스트 이름을 사용하여 해당 IP 주소 가져오기
        # 참고: 이 메서드는 때때로 127.0.0.1(루프백)을 반환할 수 있습니다.
        ip_address = socket.gethostbyname(pc_name)

        # 만약 gethostbyname이 127.0.0.1을 반환하는 경우,
        # 실제 네트워크 인터페이스의 IP를 찾기 위해 추가 조치를 시도할 수 있지만,
        # 표준 라이브러리만 사용하는 경우 gethostbyname이 가장 일반적입니다.

        return pc_name, ip_address

    except socket.error as e:
        print(f"오류 발생: {e}")
        return None, None


def terminate_premiere_process():
    """
    Windows 명령어를 사용하여 Adobe Premiere Pro 프로세스를 강제로 종료합니다.
    """
    # /F: 강제 종료 (Force)
    # /IM: 이미지 이름 (Image Name)
    command = 'taskkill /F /IM "Adobe Premiere Pro.exe"'

    try:
        # CMD 창을 숨기고 실행 (자세한 내용은 이전 대화에서 다뤘습니다.)
        result = subprocess.run(command, shell=True, check=True,
                                capture_output=True, text=True, encoding='cp949',
                                creationflags=0x08000000)

        # taskkill은 종료된 프로세스가 없어도 에러를 낼 수 있으므로, stderr를 확인합니다.
        if "SUCCESS" in result.stdout.upper():
            print("✅ Adobe Premiere Pro 프로세스를 성공적으로 종료했습니다.")
        elif "NOT FOUND" in result.stderr.upper() or "NOT FOUND" in result.stdout.upper():
            print("ℹ️ Adobe Premiere Pro 프로세스가 이미 종료되어 있습니다.")
        else:
            print("⚠️ 프로세스 종료 명령이 실행되었으나, 추가 출력 확인이 필요합니다.")
            # print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"❌ taskkill 명령어 실행 실패: {e.stderr}")



def clean_adobe_media_cache():
    """
    모든 Windows 사용자 계정 폴더에서 Adobe Media Cache 및
    Media Cache Files 폴더의 내용을 삭제합니다. (5시간 초과 파일만)
    """
    # 1. Users 폴더 경로 정의 (Windows 환경 가정)

    # 💡 삭제 기준 시간 설정 (단위: 초). 5시간 = 5 * 60 * 60 = 18000 초
    # 5시간 전에 생성된 파일만 삭제합니다.
    TIME_LIMIT_SECONDS = 5 * 60 * 60

    users_root = "C:\\Users"

    # 2. 삭제할 Adobe 캐시 폴더 목록
    cache_directories = [
        "AppData\\Roaming\\Adobe\\Common\\Media Cache Files",
        "AppData\\Roaming\\Adobe\\Common\\Media Cache"
    ]

    # 현재 시각 (Epoch Time)
    now = time.time()

    print(f"--- Adobe 미디어 캐시 정리 시작 (기준 경로: {users_root}) ---")
    print(f"--- 삭제 기준: {TIME_LIMIT_SECONDS / 3600}시간 ({TIME_LIMIT_SECONDS}초) 이상 된 파일만 삭제합니다. ---")

    # 3. Users 폴더 내의 모든 항목을 반복 (사용자 이름 후보군)
    for user_folder in os.listdir(users_root):
        # 시스템 폴더는 건너뜁니다.
        if user_folder in ['All Users', 'Default User', 'Default', 'Public', 'desktop.ini']:
            continue

        # 삭제된 파일 수를 세기 위한 변수
        deleted_count = 0
        user_processed = False

        # 4. 정의된 각 캐시 폴더 경로에 대해 삭제 작업 수행
        for cache_dir_suffix in cache_directories:
            full_cache_path = os.path.join(users_root, user_folder, cache_dir_suffix)

            # 5. 해당 경로가 실제로 존재하는지 확인
            if os.path.exists(full_cache_path):
                print(f"\n[✔️ 발견된 캐시 폴더]: {full_cache_path}")
                user_processed = True

                try:
                    # 폴더 내의 모든 파일과 하위 폴더 삭제
                    for item_name in os.listdir(full_cache_path):
                        item_path = os.path.join(full_cache_path, item_name)

                        # 💡 파일/폴더의 생성 시각을 가져옵니다.
                        # *주의: Windows에서는 getctime()이 생성 시각이 아닌 최종 메타데이터 변경 시각을 반환할 수도 있습니다.
                        creation_time = os.path.getctime(item_path)

                        # 💡 생성된 지 5시간(TIME_LIMIT_SECONDS)이 지났는지 확인
                        if (now - creation_time) > TIME_LIMIT_SECONDS:

                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                deleted_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                deleted_count += 1

                    print(f"[✅ 성공]: '{user_folder}' 계정에서 총 {deleted_count}개의 오래된 캐시 항목이 삭제되었습니다.")

                except PermissionError:
                    print(f"[❌ 권한 오류]: '{user_folder}' 계정의 파일을 삭제할 권한이 없습니다. (Adobe 프로그램이 실행 중이거나 관리자 권한이 필요할 수 있습니다.)")
                except Exception as e:
                    print(f"[❌ 오류 발생]: 캐시 정리 중 오류 발생 - {e}")


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



def find_files_with_phrase_in_targetfolder(target_folder, extension, phrase):
    """
    target_folder 내의 파일 중 특정 확장자를 가진 파일을 열어
    문구가 포함된 경우 해당 파일의 전체 경로(full_path)를 반환합니다.

    Args:
        target_folder (str): 검색할 대상 폴더 경로
        extension (str): 검색할 파일 확장자 (예: '.txt', 'xml')
        phrase (str): 파일 내에서 찾을 문구

    Returns:
        list: 문구가 포함된 파일들의 전체 경로 리스트
    """
    found_paths = []

    # 확장자에 점(.)이 없으면 자동으로 붙여줌 (예: "txt" -> ".txt")
    if not extension.startswith('.'):
        extension = '.' + extension

    # 대소문자 구분 없이 확장자 비교를 위해 소문자로 변환
    extension = extension.lower()

    # os.walk를 사용하여 하위 폴더까지 모두 탐색
    for root, dirs, files in os.walk(target_folder):
        for file_name in files:
            # 확장자 확인
            if file_name.lower().endswith(extension):
                full_path = os.path.join(root, file_name)

                try:
                    # 파일 읽기 (인코딩 오류 무시 설정으로 안전하게 읽기)
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                        # 문구가 내용에 있는지 확인
                        if phrase in content:
                            found_paths.append(full_path)

                except Exception as e:
                    print(f"파일 읽기 오류 ({full_path}): {e}")
                    continue

    if found_paths:
        return found_paths[0]
    else:
        return None  # 또는 "못 찾음" 등의 메시지나 False


# print(find_files_with_phrase("C:\Adobe_Cache",".mcdb","PGM02-Clip0001-308770.mxf 48000.pek"))

def move_file_force(target_folder, file_path):
    """
    file_path의 파일을 target_folder로 이동합니다.
    - 대상 폴더에 같은 이름의 파일이 있으면 삭제 후 이동(덮어쓰기)합니다.
    - 이동 후 원본 파일은 사라집니다.
    - 성공 시 True, 실패 시 False를 반환합니다.
    """
    try:
        # 1. 원본 파일이 존재하는지 확인
        if not os.path.exists(file_path):
            print(f"Error: 원본 파일이 없습니다. ({file_path})")
            return False

        # 2. 타겟 폴더가 없으면 생성 (안전장치)
        os.makedirs(target_folder, exist_ok=True)

        # 3. 이동할 목적지의 전체 경로 생성
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(target_folder, file_name)

        # 4. 목적지에 이미 파일이 있다면 삭제 (확실한 덮어쓰기)
        if os.path.exists(dest_path):
            os.remove(dest_path)

        # 5. 파일 이동 (다른 드라이브 간 이동도 처리함)
        shutil.move(file_path, dest_path)

        return True

    except Exception as e:
        print(f"File Move Failed: {e}")
        return False
def copy_file_force(target_folder, file_path):
    """
    file_path의 파일을 target_folder로 복사(Copy)합니다.
    - 대상 폴더에 같은 이름의 파일이 있으면 삭제 후 복사(덮어쓰기)합니다.
    - 원본 파일은 그대로 유지됩니다.
    - 성공 시 True, 실패 시 False를 반환합니다.
    """
    try:
        # 1. 원본 파일이 존재하는지 확인
        if not os.path.exists(file_path):
            print(f"Error: 원본 파일이 없습니다. ({file_path})")
            return False

        # 2. 타겟 폴더가 없으면 생성 (안전장치)
        os.makedirs(target_folder, exist_ok=True)

        # 3. 복사할 목적지의 전체 경로 생성
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(target_folder, file_name)

        # 4. 목적지에 이미 파일이 있다면 삭제 (확실한 덮어쓰기 보장)
        if os.path.exists(dest_path):
            os.remove(dest_path)

        # 5. 파일 복사
        # shutil.copy2는 파일의 내용뿐만 아니라 메타데이터(수정 시간, 권한 등)도 함께 복사합니다.
        shutil.copy2(file_path, dest_path)

        return True

    except Exception as e:
        print(f"File Copy Failed: {e}")
        return False