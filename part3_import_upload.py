import datetime
from typing import Union  # Python 3.9 이하 버전 호환을 위해 Union 사용
import shutil
import time  # (테스트용)
import re
import os
from pathlib import Path
import config
import part1_ui
import part2_sync

def filter_non_existent_files(file_list: list) -> list:
    """
    주어진 파일 경로 리스트를 순회하며, 실제로 시스템에 존재하는 파일만 남겨 반환합니다.

    Args:
        file_list (list): 파일의 풀 경로(Full Path) 문자열 리스트.

    Returns:
        list: 실제로 존재하는 파일 경로만 포함된 새로운 리스트.
    """
    cleaned_file_list = []

    print("--- 파일 존재 여부 확인 시작 ---")

    for file_path_str in file_list:
        # 문자열 경로를 Path 객체로 변환합니다.
        path_obj = Path(file_path_str)

        # .exists() 메서드를 사용하여 파일이 실제로 존재하는지 확인합니다.
        if path_obj.exists():
            cleaned_file_list.append(file_path_str)
            print(f"✅ 존재함: {file_path_str}")
        else:
            # 존재하지 않는 파일은 리스트에서 제외됩니다.
            print(f"❌ 제외함 (찾을 수 없음): {file_path_str}")

    print("--- 파일 존재 여부 확인 완료 ---")
    return cleaned_file_list

import os


def check_byte_value(file_full_path: str, sequence_number: int, expected_hex_value: str) -> bool:
    """
    주어진 파일 경로에서 특정 순서번호(1부터 시작)의 1바이트 값이
    예상되는 16진수 값과 일치하는지 확인합니다.

    Args:
        file_full_path (str): 확인할 파일의 전체 경로 (Full Path).
        sequence_number (int): 확인할 바이트의 순서번호 (1부터 시작).
        expected_hex_value (str): 예상되는 16진수 값 (예: "0x13", "13", "0xa1").

    Returns:
        bool: 값이 일치하면 True, 아니면 False를 반환합니다.
    """
    # 1. 파일 존재 여부 및 유효성 검사
    if not os.path.exists(file_full_path):
        print(f"오류: 파일을 찾을 수 없습니다: {file_full_path}")
        return False

    # 2. 예상 값 처리 및 변환
    try:
        # "0x" 접두사를 제거하고 16진수 문자열을 정수(0-255)로 변환합니다.
        # 예: "0x13" -> 19, "13" -> 19
        cleaned_hex = expected_hex_value.lower().replace("0x", "")
        expected_int_value = int(cleaned_hex, 16)

        # 1바이트 범위(0-255)를 벗어나는 값은 유효하지 않음
        if not (0 <= expected_int_value <= 255):
            print(f"오류: 예상 값 '{expected_hex_value}'은(는) 유효한 1바이트(0x00 ~ 0xFF) 범위를 벗어납니다.")
            return False

    except ValueError:
        print(f"오류: 예상 값 '{expected_hex_value}'은(는) 올바른 16진수 형식이 아닙니다.")
        return False

    # 3. 파일 읽기 및 위치 이동
    try:
        # 'rb' (read binary) 모드로 파일을 엽니다.
        with open(file_full_path, 'rb') as f:
            # 순서번호는 1부터 시작하므로, 파일 포인터는 (순서번호 - 1) 위치로 이동합니다.
            byte_position = sequence_number - 1

            # 파일의 끝으로 이동하여 파일 크기를 확인합니다.
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            if byte_position < 0:
                print(f"오류: 순서번호는 1 이상이어야 합니다. 현재 입력: {sequence_number}")
                return False

            if byte_position >= file_size:
                # 요청한 위치가 파일 크기를 벗어난 경우
                print(f"오류: 파일 크기는 {file_size} 바이트입니다. {sequence_number}번째 바이트는 존재하지 않습니다.")
                return False

            # 원하는 위치로 포인터를 다시 이동시킵니다.
            f.seek(byte_position)

            # 4. 1 바이트 읽기
            read_byte = f.read(1)

            # 읽은 바이트(bytes 객체)를 정수(int)로 변환합니다.
            # read_byte[0]은 읽은 1바이트의 정수 값을 반환합니다.
            actual_int_value = read_byte[0]

            # 5. 값 비교
            is_match = (actual_int_value == expected_int_value)

            # 결과를 좀 더 자세히 출력합니다. (디버깅 목적)
            actual_hex = f"0x{actual_int_value:02x}"
            print(f"경로: {file_full_path}")
            print(f"순서번호: {sequence_number} ({byte_position}번 인덱스)")
            print(f"실제 값: {actual_hex} | 예상 값: {expected_hex_value}")

            return is_match

    except IOError as e:
        print(f"오류: 파일을 읽는 중 I/O 문제가 발생했습니다. ({e})")
        return False
    except Exception as e:
        print(f"예상치 못한 오류 발생: {e}")
        return False


# path =r"C:\Users\sezli\OneDrive\바탕 화면\새 폴더 (2)\만드는중.pek"
# path2 =r"C:\Users\sezli\OneDrive\바탕 화면\새 폴더 (2)\다만든mov.pek"
#
#
# print(check_byte_value(path2,61,"0x01"))

# def wait_for_file_stability(file_path: str, n_cycles: int, check_interval_sec: int = 20) -> bool:
#     """
#     파일이 안정화될 때까지 정해진 주기와 횟수만큼 모니터링합니다.
#
#     파일을 'check_interval_sec' 간격으로 'n_cycles' 만큼 확인합니다.
#     두 번의 연속된 확인에서 파일의 바이너리 내용이 동일하면 파일이 안정화된 것으로
#     간주하고 True를 반환합니다.
#
#     Args:
#         file_path (str): 모니터링할 파일의 경로
#         n_cycles (int): 최대 확인할 횟수 (사이클)
#         check_interval_sec (int): 확인 주기 (초). 기본값은 20초입니다.
#
#     Returns:
#         bool: 파일이 안정화되었으면 True, N번의 사이클 동안 계속 변경되거나
#               파일을 찾을 수 없으면 False를 반환합니다.
#     """
#     print(f"'{file_path}' 파일 안정화 모니터링 시작... (최대 {n_cycles}회, {check_interval_sec}초 간격)")
#
#     # 이전 사이클에서 읽은 파일 데이터를 저장할 변수
#     previous_data = None
#
#     for i in range(n_cycles):
#         current_data = None
#         print(f"피크파일 을 {n_cycles}주기로 확인합니다.")
#         try:
#             # 1. 파일을 바이너리('rb') 모드로 읽습니다.
#             with open(file_path, 'rb') as f:
#                 current_data = f.read()
#
#         except FileNotFoundError:
#             print(f"  [사이클 {i + 1}/{n_cycles}] 파일이 아직 없습니다.")
#             # 파일이 없으면 current_data는 None으로 유지됩니다.
#
#         except PermissionError:
#             print(f"  [사이클 {i + 1}/{n_cycles}] 파일 접근 권한 없음 (아직 쓰기 중일 수 있습니다).")
#             # 파일이 잠겨있으면 current_data는 None으로 유지됩니다.
#
#         except Exception as e:
#             print(f"  [사이클 {i + 1}/{n_cycles}] 파일 읽기 오류: {e}")
#             # 기타 오류 발생 시
#
#         # --- 안정화 확인 로직 ---
#         # 2. current_data가 None이 아니고 (즉, 파일이 존재하고 성공적으로 읽힘)
#         # 3. previous_data와 내용이 동일한지 확인합니다.
#         if current_data is not None and current_data == previous_data:
#             print(f"\n✅ [사이클 {i + 1}/{n_cycles}] 파일이 안정화되었습니다. (크기: {len(current_data)} 바이트)")
#             return True
#
#         # --- 다음 사이클 준비 ---
#         # 4. 안정화되지 않았으므로, 현재 데이터를 '이전 데이터'로 저장합니다.
#         previous_data = current_data
#
#         # 5. 마지막 사이클이 아닐 경우, 다음 확인까지 대기합니다.
#         if i < n_cycles - 1:
#             if current_data is None:
#                 # 파일이 없거나 읽을 수 없는 경우
#                 pass  # 위에서 이미 로그를 찍었으므로 추가 로그 없이 대기
#             else:
#                 # 파일은 있지만 내용이 바뀐 경우
#                 print(f"  [사이클 {i + 1}/{n_cycles}] 파일 내용이 변경되었습니다 (현재 크기: {len(current_data)} 바이트).")
#
#             time.sleep(check_interval_sec)

def wait_for_file_stability(file_path: str, n_cycles: int, check_interval_sec: int = 20) -> bool:
    """
    파일 내용이 두 번 연속 동일하고, 생성 시간과 수정 시간이 다를 때 안정화된 것으로 판단합니다.
    (수정 시간 != 생성 시간은 파일에 쓰기 작업이 완료되었음을 증명합니다.)
    """
    path_obj = Path(file_path)
    print(f"'{file_path}' 파일 안정화 모니터링 시작... (최대 {n_cycles}회, {check_interval_sec}초 간격)")

    previous_data = None

    for i in range(n_cycles):
        current_data = None
        current_ctime = None
        current_mtime = None
        print(f"피크파일 을 {i + 1}/{n_cycles}주기로 확인합니다.")

        # 1. 파일 상태(Stat) 정보 및 내용 확인
        try:
            stat_info = path_obj.stat()
            current_ctime = stat_info.st_ctime  # 생성 시간 (Creation Time)
            current_mtime = stat_info.st_mtime  # 수정 시간 (Modification Time)
            print(f"수정시간입니다 {current_mtime}")
            print(f"생성시간 입니다 {current_ctime}")
            with open(file_path, 'rb') as f:
                current_data = f.read()

        except FileNotFoundError:
            print(f"  [사이클 {i + 1}] 파일이 아직 없습니다.")
        except PermissionError:
            print(f"  [사이클 {i + 1}] 파일 접근 권한 없음 (아직 쓰기 중일 수 있습니다).")
        except Exception as e:
            print(f"  [사이클 {i + 1}] 파일 읽기 오류: {e}")

        # --- 안정화 최종 확인 로직 ---

        # 🌟 조건 1: 파일 내용이 두 번 연속 동일한지 확인 (Content Stability)
        is_content_stable = (current_data is not None and current_data == previous_data)

        # 🌟 조건 2: 생성 시간과 수정 시간이 다른지 확인 (Activity/Completion Check)
        #           Windows 환경에서 파일이 쓰여지면 이 두 값은 달라집니다.
        has_been_modified = (current_ctime is not None and current_mtime is not None and current_ctime != current_mtime)

        if is_content_stable and has_been_modified:
            # 두 조건 모두 만족 시 안정화 완료
            print(f"\n✅ [사이클 {i + 1}/{n_cycles}] 파일이 안정화되었습니다. (크기: {len(current_data)} 바이트)")
            print(f"  [시간 정보] 생성: {time.ctime(current_ctime)}, 최종 수정: {time.ctime(current_mtime)}")
            return True

        # --- 다음 사이클 준비 ---
        previous_data = current_data

        if i < n_cycles - 1:
            if current_data is not None and not is_content_stable:
                print(f"  [사이클 {i + 1}] 파일 내용이 변경되었습니다 (현재 크기: {len(current_data)} 바이트).")
            elif current_data is not None and is_content_stable and not has_been_modified:
                # 내용이 멈췄지만, 아직 생성/수정 시간이 같아 초기 상태로 판단됨
                print(f"  [사이클 {i + 1}] 내용 동일, 하지만 아직 쓰기 작업 완료 증거(MTime!=CTime)가 부족합니다.")


            # if i > n_cycles - 10:
            #     print("충분한 탐색중에도 이런 결과를 보인다면 완료 된것으로 판단하겠습니다.")
            #     return True
            # #### 이 부분 답 없는거 같은데 ;;
            time.sleep(check_interval_sec)

    # N번의 사이클이 모두 끝날 때까지 True가 반환되지 않으면, False를 반환합니다.
    print(f"\n❌ {n_cycles}번의 사이클 동안 파일이 안정화되지 않았습니다.")
    return False

def change_extension_and_fill_content_if_txt(path: str, new_extension: str, content: str):
    """
    주어진 파일의 확장자를 변경하고, 변경된 확장자가 '.txt'인 경우에만
    주어진 content로 파일 내용을 덮어씁니다.

    Args:
        path (str): 확장자를 변경할 원본 파일의 경로.
        new_extension (str): 변경할 새로운 확장자 (예: '.log', 'txt').
                             '.'을 포함하지 않아도 내부적으로 처리합니다.
        content (str): 새 확장자가 '.txt'일 경우 파일에 작성할 내용.

    Returns:
        str | bool: 작업 성공 시 새 파일의 전체 경로(Full Path) 문자열을 반환합니다.
                    작업 실패 시 False를 반환합니다.
    """

    # 1. 경로 및 확장자 처리
    original_path = Path(path)

    # 확장자가 '.'으로 시작하도록 정규화
    if not new_extension.startswith('.'):
        new_extension = '.' + new_extension

    # 새로운 파일 경로 생성 (이름은 유지하고 확장자만 변경)
    new_path = original_path.with_suffix(new_extension)

    print(f"원본 파일: {original_path.name}")
    print(f"새 경로: {new_path.name}")

    # 2. 파일 이름 변경 (확장자 변경)
    try:
        if not original_path.exists():
            print(f"❌ 오류: 원본 파일을 찾을 수 없습니다: {path}")
            return False

        # os.rename을 사용하여 파일 이름 변경
        os.rename(original_path, new_path)
        print(f"✅ 확장자 변경 완료: {original_path.name} -> {new_path.name}")

    except OSError as e:
        print(f"❌ 오류: 파일 이름 변경 실패 ({original_path.name} -> {new_path.name}). 사유: {e}")
        try:
            os.remove(original_path)
        except OSError as e:
            pass
        return False

    # 3. 확장자가 '.txt'인 경우 내용 작성
    if new_path.suffix.lower() == '.txt':
        try:
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ 텍스트 파일 내용 작성 완료.")

        except IOError as e:
            print(f"❌ 오류: 텍스트 파일 내용 작성 실패. 사유: {e}")
            return False

    else:
        print("ℹ️ 새 확장자가 '.txt'가 아니므로 내용 작성은 건너뜁니다.")

    # 4. 성공 시 새 파일의 전체 경로 반환
    return str(new_path.resolve())






def find_first_target_path(source_path: str, target_path: str, ext_list: list) :
    """
    source_path의 하위 폴더를 재귀적으로 탐색하여,
    ext_list에 포함된 확장자를 가진 첫 번째 파일을 찾습니다.

    발견 즉시, (조합된 타겟 경로 문자열, 원본 파일의 전체 경로 문자열)을 튜플로 반환합니다.
    찾지 못하면 None을 반환합니다.

    Args:
        source_path (str): 탐색을 시작할 소스 디렉터리 경로
        target_path (str): 조합의 기준이 될 타겟 디렉터리 경로
        ext_list (list): 찾고자 하는 확장자 리스트 (예: ['.mxf', '.wav'])

    Returns:
        tuple[str, str] | None:
            (조합된 타겟 경로 문자열, 원본 파일의 전체 경로 문자열) 튜플 또는 None
    """

    # 1. 경로를 Path 객체로 변환
    source_p = Path(source_path)
    target_p = Path(target_path)

    # 2. 확장자 비교를 위해 소문자 Set으로 변환 (빠른 조회를 위해)
    allowed_ext_set = {ext.lower() for ext in ext_list if ext.startswith('.')}

    if not allowed_ext_set:
        print("[경고] 유효한 확장자 목록(ext_list)이 없습니다.")
        return None


    ###  테스트용 추가

    for add_path in config.pgm:
        print(f"{add_path}을 추가합니다.")
        add_source_p = source_p / add_path
        add_target_p = target_p / add_path
        print(f"소스p ={add_source_p}, 타겟 ={add_target_p}")

    # 3. .rglob('*')로 모든 하위 파일 및 폴더를 재귀적으로 탐색
        for file_path in  add_source_p.rglob("*"):

            if not os.path.exists(str(file_path.resolve())):
                continue
            if file_path.suffix == '.txt':
                print(f"텍스트 파일 발견: {file_path}")
                full_path_str = str(file_path.resolve())
                tag_str = part2_sync.read_txt_tag(full_path_str, "TIME_STAMP")
                print("txt 파일의 타임스템프를 확인해보겠습니다 (5분이상 경과된 txt는 멈춘걸로 간주하고 삭제)")
                print(tag_str)
                # 1-2. strptime 전에 None(읽기실패) 또는 빈문자열 확인
                if not tag_str:
                    print("타임스템프 태그를 읽을 수 없습니다.")
                    if os.path.exists(full_path_str):
                        os.remove(full_path_str)
                    continue

                    # 1-3. 시간 문자열 파싱 및 비교
                time_format = "%Y-%m-%d %H:%M:%S"  # 초까지 나오는 포맷
                saved_time = datetime.datetime.strptime(tag_str, time_format)

                if datetime.datetime.now() - saved_time < datetime.timedelta(
                        minutes=5):
                    print("최신 파일임으로 스킵합니다.")
                    continue  # N분 이내 (최신이므로 스킵)
                else:
                    print("최신화가 5분 이상 경과된 파일 작동이 멈춘것으로 간주하고 새로 만듭니다.")
                    os.remove(full_path_str)  ###TXT 파일 삭제하고
                    time.sleep(5)
                    continue  # N분 지남 (오래됐으므로 생성)




            # 4. 파일이면서, 확장자가 ext_list에 포함되는지 확인
            if file_path.is_file() and (file_path.suffix.lower() in allowed_ext_set):
                # 5. 첫 번째 일치하는 파일 발견!

                # (예: '20251111/clip1.mxf')
                relative_path = file_path.relative_to(add_source_p)

                # (예: 'C:/Target' / '20251111/clip1.mxf')
                final_target_path = add_target_p / relative_path

                # 6. 두 경로를 문자열로 변환하여 튜플로 반환
                print(f"발견된 링크본 파일: {file_path}")
                print(f"조합된 타겟 경로: {final_target_path}")

                if os.path.exists(final_target_path):
                    print(f"'{final_target_path}'이(가) 존재합니다.")
                    return (str(final_target_path), str(file_path))
                else:
                    print(f"'{final_target_path}'이(가) 존재하지 않습니다.")

                    try:
                        os.remove(file_path)
                    except:
                        print("없는 파일이라 링크를 삭제하려 하나 파일이 삭제되지 않았습니다.")


                    continue

                # 🚨 반환 값이 (조합된 타겟 경로, 원본 파일의 전체 경로) 튜플로 변경됨


            # 7. 루프가 끝날 때까지 아무것도 찾지 못함
    print("일치하는 파일을 찾지 못했습니다.")
    return None,None



def write_txt_tag_and_content(file_path: str, tag_name: str, content_to_write) -> bool:
    """
    파일의 다른 내용은 유지하면서, 지정된 태그의 내용만 수정하거나 추가합니다.

    - [CASE 1] 파일에 <tag>가 이미 있으면: 내용만 교체합니다.
    - [CASE 2] 파일에 <tag>가 없으면: 파일 맨 밑에 <tag>내용</tag>을 추가합니다.
    - [CASE 3] 파일이 아예 없으면: <tag>내용</tag>만 있는 새 파일을 만듭니다.

    Args:
        file_path (str): 저장할 파일의 전체 경로
        tag_name (str): 생성할 태그 이름 (예: "last_work_time")
        content_to_write (Union[str, datetime.datetime]): 태그 사이에 쓸 텍스트 내용 또는 datetime 객체

    Returns:
        bool: 쓰기 성공 시 True, 실패 시 False
    """

    # 1. 인자로 받은 내용(datetime 또는 str)을 최종 문자열로 변환
    content_str = ""
    if isinstance(content_to_write, datetime.datetime):
        # datetime 객체이면, 표준 형식의 '문자열'로 변환
        content_str = content_to_write.strftime("%Y-%m-%d %H:%M:%S")
    else:
        # datetime 객체가 아니면 (str, int 등), 그냥 문자열로 취급
        content_str = str(content_to_write)

    # 2. 정규식 패턴 및 교체할 문자열 준비
    # re.DOTALL: .이 줄바꿈 문자(\n)도 포함하게 하여 여러 줄에 걸친 태그도 인식
    regex_pattern = rf'<{tag_name}>(.*?)</{tag_name}>'
    replacement_str = f"<{tag_name}>{content_str}</{tag_name}>"

    try:
        # 3. 파일 읽기를 먼저 시도
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

        except FileNotFoundError:
            # [CASE 3] 파일이 아예 없는 경우 -> 새 파일 생성
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(replacement_str)  # 새 태그만 씀
            return True

        # 4. 파일이 존재하는 경우, 태그 교체 시도
        # re.subn()은 (수정된내용, 교체횟수)를 반환함
        new_content, count = re.subn(regex_pattern,
                                     replacement_str,
                                     original_content,
                                     count=1,  # 첫 번째 일치하는 태그만 교체
                                     flags=re.DOTALL)

        if count > 0:
            # [CASE 1] 태그가 존재하여 교체됨 (count=1)
            pass  # new_content에 이미 수정된 내용이 들어있음
        else:
            # [CASE 2] 태그가 존재하지 않아 추가함 (count=0)
            # 원본 내용 맨 뒤에 (줄바꿈 후) 새 태그 추가
            new_content = original_content.rstrip('\n') + '\n' + replacement_str

        # 5. 최종본(new_content)을 파일에 덮어쓰기
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True  # 성공

    except PermissionError:
        print(f"[오류] 파일 쓰기 권한이 없습니다: {file_path}")
        return False
    except Exception as e:
        print(f"[오류] 파일 처리 중 ({file_path}): {e}")
        return False



def check_make_finish(
        source: str,
        target: str,
        check_ext_list: list[str],
        unupload_ext_list: list[str],
        delete: bool = True,
        skip_size_kb_of_pekfile=20
) -> bool:


    source_p = Path(source).resolve()
    target_p = Path(target).resolve()

    # --- 1. 안전성 및 초기화 검사 ---
    if source_p == target_p:
        print(f"[오류] 소스와 타겟 경로가 동일합니다: {source_p}")
        return False
    if not source_p.exists():
        print(f"[오류] 소스 폴더를 찾을 수 없습니다: {source_p}")
        return False
    if str(target_p).startswith(str(source_p)):
        print(f"[오류] 타겟 폴더가 소스 폴더의 하위에 있습니다: {target_p}")
        return False

    target_p.mkdir(parents=True, exist_ok=True)

    # 검사 확장자 집합 및 제외(Unupload) 확장자 집합 생성
    check_ext_set = {ext.lower() for ext in check_ext_list if ext.startswith('.')}
    unupload_ext_set = {ext.lower() for ext in unupload_ext_list if ext.startswith('.')}

    print(f"--- 피크파일 완성 조건  판단. ---")
    # print(f"소스: {source_p}")
    # print(f"**검사 대상 확장자:** {check_ext_set}")
    # print(f"**제외 대상 확장자:** {unupload_ext_set}")

    if not check_ext_set:
        print("[오류] 검사할 확장자 목록(check_ext_list)이 유효하지 않습니다. 이번사이클에 검사 항목 확장자가 없습니다.")
        return False

    # --- 2. 조건 검사 대상 파일들 수집 ---
    files_to_check = []
    # rglob을 사용하여 하위 폴더까지 재귀적으로 탐색
    for f in source_p.rglob("*"):
        if f in config.for_peak_out_file_list:
            continue
        if f.is_file() and f.suffix.lower() in check_ext_set:
            files_to_check.append(f)

    # --- 3. 조건 판별 ---
    condition_met = False
    if not files_to_check:
        print("[검사 중단] check_ext_list에 해당하는 검사 대상 파일이 소스에 없습니다.")
        return False
    else:
        all_are_different = True
        print(f"  -> {len(files_to_check)}개의 파일을 검사합니다.")

        for f in files_to_check:
            print(f"{f}파일에 대한 업로드 검사를 시작합니다.")
            print(f"{config.for_peak_out_file_list}")
            if f in config.for_peak_out_file_list:
                print("예외 항목에 해당함으로 넘어갑니다")
                continue
            try:
                if f.suffix.lower() == ".pek":
                    size_bytes = f.stat().st_size
                    # 2. 바이트를 킬로바이트(KB)로 변환 (1 KB = 1024 Bytes)
                    size_kb = size_bytes / 1024
                    if size_kb <= skip_size_kb_of_pekfile:
                        all_are_different = True
                        print("20kb 이하의 pek파일임으로 생성시간 수정시간 여부와 상관없이 완료로 취급합니다.")
                        time.sleep(20)
                        condition_met = True
                        break

                if wait_for_file_stability(f,10000):
                    all_are_different = True
                else:
                    all_are_different = False
                    break
            except FileNotFoundError:
                print(f"  [경고] 파일 검사 중 사라짐: {f}")

        if all_are_different:
            print("  [조건 일치] 피크생성이 완료되었습니다")
            condition_met = True

        return condition_met


def extract_file_path_from_winerror(error_message: str) -> str:
    """
    WinError 32 오류 메시지 문자열에서 단일 인용부호(')로 묶인 파일 경로를 추출합니다.

    Args:
        error_message (str): Exception 변수(e)의 문자열 메시지.

    Returns:
        str: 추출된 파일 경로 또는 찾지 못했을 경우 빈 문자열.
    """
    try:
        # 1. 첫 번째 단일 인용부호(')가 시작되는 위치를 찾습니다.
        start_index = error_message.find("'")

        # 2. 첫 번째 인용부호 이후에 오는 두 번째 단일 인용부호(')가 닫히는 위치를 찾습니다.
        #   (start_index + 1 부터 검색 시작)
        end_index = error_message.find("'", start_index + 1)

        # 3. 인덱스가 유효한 경우, 그 사이의 문자열을 추출합니다.
        if start_index != -1 and end_index != -1 and start_index < end_index:
            # 시작 위치 다음 문자부터 끝 위치 바로 앞 문자까지 슬라이싱합니다.
            file_path = error_message[start_index + 1: end_index]
            return file_path

        else:
            return ""  # 경로를 찾지 못함

    except Exception:
        # 혹시 모를 예외 발생 시 빈 문자열 반환
        return ""

def upload_file_if_conditions_met(
        source: str,
        target: str,
        unupload_ext_list: list[str],
        unchecked_file_list,
        delete: bool = True,
) -> bool:


    source_p = Path(source).resolve()
    target_p = Path(target).resolve()

    print("삭제 작업에 들어갑니다.")

    print(f"\n--- 2. 전체 파일 '이동' 작업 시작 (제외 목록 적용) ---")

    move_success = True

        # 소스 폴더의 모든 내용물 (폴더 포함)을 탐색
    for item in source_p.rglob('*'):

        if item in config.for_peak_out_file_list:
            print("이전에 작업했던 파일이기에 건너 뜁니다.")
            continue # 이전에 했던 파일이면 건너 뜁니다.

        # 소스 폴더 내에서의 상대 경로를 계산
        relative_path = item.relative_to(source_p)
        target_item_path = target_p / relative_path

        if item.is_dir():
            # 폴더 구조 유지: 타겟 경로에 폴더가 없으면 생성 (이미 존재하면 무시)
            target_item_path.mkdir(parents=True, exist_ok=True)

        elif item.is_file():
            # **제외 목록 검사**
            if item.suffix.lower() in unupload_ext_list:
                print(f"  [제외] unupload_ext_list에 해당하여 건너뜀: {item.name}")
                continue

            if item in unchecked_file_list:
            #if item.name.lower() in unchecked_file_list:
                print("검사 예외 항목입니다.")
                continue


            # 파일 복사: 타겟에 파일이 이미 존재하면 건너뛰기
            if target_item_path.exists():
                print(f"  [건너뛰기] 타겟에 파일이 이미 존재합니다: {target_item_path}")
            else:
                # 파일 복사 (copy2는 메타데이터 유지)
                shutil.copy2(item, target_item_path)
                print(f"  [복사 완료] {item.name}")
            try:
                # 복사 성공 후 원본 파일 삭제
                if delete:
                    item.unlink()
                    print(f"  [원본 삭제] {item.name}")

            except Exception as e:
                print(f" 파일 복사/삭제 중 실패 한번에 모아서 범퍼 파일을 넣어 pek를 물지 않게 하겠습니다.: {item.name} -> {e}")

                move_success = False

                error_message_str = str(e)
                locked_file_full_path = extract_file_path_from_winerror(error_message_str)
                ## 실패한 파일의 full_경로 추출



                if locked_file_full_path:
                    # 3. PEK 확장자 확인 후 리스트에 추가
                    try:
                        file_path_obj = Path(locked_file_full_path)

                        # 확장자가 '.pek'인지 확인 (대소문자 무시)
                        if file_path_obj.suffix.lower() == ".pek":

                            # config.last_pek_file_path가 리스트임을 가정하고 append
                            config.last_pek_file_path.append(locked_file_full_path)

                            print(f"  [PEK 경로 저장] 잠금된 PEK 파일 경로를 리스트에 추가했습니다: {locked_file_full_path}")
                            print(f"  [현재 리스트 개수] {len(config.last_pek_file_path)}개")

                        else:
                            print(f"  [정보] 추출된 파일의 확장자가 '.pek'이 아니므로 저장하지 않습니다: {file_path_obj.suffix}")

                    except Exception as path_e:
                        print(f"  [경고] Path 객체 변환 중 오류 발생: {path_e}")
    part1_ui.clear_subfolders_in_cache(source_p)
    config.for_peak_out_file_list = filter_non_existent_files(config.for_peak_out_file_list) #리스트에 있지만 현재 실제로 없는 파일 삭제

    temp = set(config.for_peak_out_file_list)
    config.for_peak_out_file_list = list(temp)  ## 중복제거

    print(f"config.for_peak_out_file_list의 갯수: {len(config.for_peak_out_file_list)}")
    time.sleep(3)
    for item in source_p.rglob('*'):
        # rglob('*')은 파일뿐만 아니라 디렉터리도 반환하므로, 파일인지 먼저 확인하는 것이 안전합니다.
        if item.is_file():
            # item.suffix는 파일의 확장자(예: '.pek', '.jpg')를 반환합니다.
            if item.suffix == '.pek':
                config.for_peak_out_file_list.append(item)
                ## parent 안하면 wondowpath가 앞에 붙어서 나옴


    return True




def check_make_finish_by_binary(list_of_pek):
    status = False
    for path in list_of_pek:
        if check_byte_value(path,61,"0x01"):
            status = True
        else:
            status = False

    return status
