import os
import re
import datetime
from pathlib import Path
from typing import Union  # Python 3.9 이하 버전 호환을 위해 Union 사용
import time
import config

def read_txt_tag(file_path: str, tag_name: str) -> Union[str, None]:
    """
    지정된 텍스트 파일에서 XML/HTML 스타일의 태그 사이의 내용을 읽어 반환합니다.
    파일 읽기 오류(FileNotFoundError, PermissionError 등) 발생 시 None을 반환합니다.

    Args:
        file_path (str): 읽을 파일의 전체 경로
        tag_name (str): 추출할 태그 이름 (예: "last_work_time")

    Returns:
        Union[str, None]: 태그 사이의 텍스트 내용 (strip() 처리됨).
                          파일이 없거나 태그를 찾지 못하면 None을 반환합니다.
    """
    # 1. 태그를 찾기 위한 정규식 동적 생성
    regex_pattern = rf'<{tag_name}>(.*?)</{tag_name}>'

    try:
        # 2. 파일을 열고 내용을 읽습니다.
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 3. 정규식을 사용하여 태그 사이의 내용을 찾습니다. (re.DOTALL)
        match = re.search(regex_pattern, content, re.DOTALL)

        if match:
            # 4. 찾은 내용(괄호 안의 그룹)을 반환합니다.
            return match.group(1).strip()
        else:
            # 태그를 찾지 못함
            return None

    except (FileNotFoundError, PermissionError, OSError):
        # print(f"[오류] 파일 읽기 실패 ({file_path})") # 디버깅 시 주석 해제
        return None  # 파일 읽기 자체를 실패
    except Exception as e:
        # print(f"[오류] 알 수 없는 오류 ({file_path}): {e}") # 디버깅 시 주석 해제
        return None


def write_txt_tag_and_content(file_path: str, tag_name: str, content_to_write: Union[str, datetime.datetime]) -> bool:
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

        # 5. 최종본(new_content)을 파일에 덮어쓰기덮어쓰기
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True  # 성공

    except PermissionError:
        print(f"[오류] 파일 쓰기 권한이 없습니다: {file_path}")
        return False
    except Exception as e:
        print(f"[오류] 파일 처리 중 ({file_path}): {e}")
        return False


def check_stem_exists(target_path: Path, txt_update_time_threshold_min: int = 5) -> bool:
    """
    타겟 경로의 부모 디렉터리에서 해당 파일의 'stem'과 일치하는 파일이 있는지 확인합니다.

    - .txt가 아닌 파일: 존재하면 True 반환 (스킵)
    - .txt 파일: 존재하고 N분 이내 갱신되었으면 True 반환 (스킵)
    - 그 외: False 반환 (파일 생성 필요)

    Args:
        target_path (Path): 생성될 파일의 전체 예상 경로
        txt_update_time_threshold_min (int): .txt 파일의 시간 임계값(분)

    Returns:
        bool: 존재하고 최신이면 True (스킵), 아니면 False (생성)
    """
    target_dir = target_path.parent
    target_stem = target_path.stem

    # 부모 디렉터리가 존재하지 않으면, 파일도 존재할 수 없음
    if not target_dir.exists():
        return False
    try:
        # os.scandir가 listdir보다 효율적임
        for entry in os.scandir(target_dir):
            # 파일이고, 확장자 제외 이름(stem)이 일치하면
            if entry.is_file() and Path(entry.name).stem == target_stem:
                # 1. 일치하는 파일이 .txt인 경우 (시간 검사)
                if entry.name.lower().endswith(".txt"):
                    print("동일한 이름의 txt파일 발견")
                    try:
                        # 1-1. 태그 읽기
                        tag_str = read_txt_tag(entry.path, "IP_ADDRESS")
                        pc_name, ip_address = config.get_pc_info()
                        if str(tag_str) == str(ip_address):
                            print("이 PC 본인이 잘못만들거나 중간에 꺼진 파일입니다. 삭제합니다.")
                            return False


                        tag_str = read_txt_tag(entry.path, "TIME_STAMP")
                        print("txt 파일의 타임스템프를 확인해보겠습니다 (5분이상 경과된 txt는 멈춘걸로 간주하고 삭제)")
                        print(tag_str)

                        # 1-2. strptime 전에 None(읽기실패) 또는 빈문자열 확인
                        if not tag_str:
                            print("타임스템프 태그를 읽을 수 없습니다.")
                            if os.path.exists(entry.path):
                                os.remove(entry.path)
                            ## 충돌로 인해 빈 txt가 있는데 지워줘야 할 듯
                            # 태그가 없으면 오래된 파일로 간주 -> False (생성)
                            return False

                            # 1-3. 시간 문자열 파싱 및 비교

                        time_format = "%Y-%m-%d %H:%M:%S"  # 초까지 나오는 포맷
                        saved_time = datetime.datetime.strptime(tag_str, time_format)

                        if datetime.datetime.now() - saved_time < datetime.timedelta(
                                minutes=txt_update_time_threshold_min):
                            print("최신 파일임으로 스킵합니다.")
                            return True  # N분 이내 (최신이므로 스킵)
                        else:
                            print("최신화가 5분 이상 경과된 파일 작동이 멈춘것으로 간주하고 새로 만듭니다.")
                            os.remove(entry.path)  ###TXT 파일 삭제하고
                            time.sleep(5)
                            return False  # N분 지남 (오래됐으므로 생성)

                    except ValueError:
                        # 1-4. strptime에서 날짜 형식이 안 맞을 때 (ValueError)
                        print(f"❌ 오류: TXT 파일의 타임스탬프 형식이 잘못되었습니다: {tag_str}")
                        # 파싱 실패 시, 오래된 파일로 간주 -> False 반환 (생성)
                        return False

                    except OSError:
                        # 파일 삭제 중 문제 발생 시 (오래된 파일로 간주)
                        print(f"❌ TXT 파일 처리 중 OSError 발생: {entry.path}")
                        return False

                # 2. 일치하는 파일이 .txt가 아닌 경우 (예: .mxf)
                else:
                    return True  # .txt가 아닌 파일이 존재함 (스킵)

    except OSError as e:
        print(f"  [경고] 디렉터리 스캔 중 오류 발생 {target_dir}: {e}")
        # 스캔 실패 시, 일단 생성 시도 (False)
        return False

    # 3. 스캔 완료. 일치하는 stem을 가진 파일을 하나도 못 찾음
    return False

#########################################################################################################


def create_optimized_stubs(source_dir, target_dir, days_threshold,
                           exclude_folders=None, allowed_extensions=None):
    """
    소스 디렉터리를 스캔하여 'days_threshold'일 이내에 수정된 파일의
    0바이트 스텁(stub) 파일을 타겟 디렉터리에 생성합니다.

    'YYYYMMDD' 형식의 폴더명을 가진 경우 최적화 로직을 사용하며,
    'exclude_folders' 목록에 포함된 폴더는 스캔에서 제외합니다.

    [수정됨] 'allowed_extensions' 목록에 포함된 확장자만 처리합니다.
    [수정됨] 타겟 디렉터리에 확장자만 다른 동일 이름(stem)의 파일이
             이미 존재하면 0바이트 파일을 생성하지 않습니다.
    """



    # 1. 매개변수 초기화
    if exclude_folders is None:
        exclude_folders = []

    # [수정됨] 허용 확장자 목록을 소문자 Set으로 변환 (빠른 조회를 위해)
    allowed_ext_set = None
    if allowed_extensions:
        #
        allowed_ext_set = {ext.lower() for ext in allowed_extensions if ext.startswith('.')}
        if not allowed_ext_set:
            print("[경고] 'allowed_extensions'가 제공되었으나 '.'로 시작하는 유효한 확장자가 없습니다.")
            allowed_ext_set = None  #

    # 2. 기준이 되는 날짜(시간) 계산
    cutoff_dt = datetime.datetime.now() - datetime.timedelta(days=days_threshold)
    cutoff_date = cutoff_dt.date()

    print(f"--- 스캔 시작 ---")
    print(f"기준 시간: {cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')} 이후 수정된 파일")
    print(f"최적화 기준일: {cutoff_date.strftime('%Y%m%d')} 보다 오래된 날짜 폴더는 건너뜁니다.")
    print(f"제외 폴더: {exclude_folders}")
    # [수정됨] 허용 확장자 로그
    if allowed_ext_set:
        print(f"허용 확장자: {allowed_ext_set}")
    else:
        print(f"허용 확장자: (모든 파일)")
    print(f"소스: {source_dir}")
    print(f"타겟: {target_dir}")
    print(f"체크 로직: 타겟에 동일한 이름(확장자 무관)이 있으면 스킵")
    print("-" * 20)

    # os.walk를 topdown=True로 설정 (기본값)해야 dirs 목록 수정 가능
    for root, dirs, files in os.walk(source_dir, topdown=True):

        current_root_path = Path(root)

        # --- 3. 최적화 및 제외 로직 ---
        for d in dirs[:]:
            # 3-1. 요청하신 '제외 폴더' 로직
            if d in exclude_folders:
                print(f"  [제외] 지정된 폴더 제외: {current_root_path / d}")
                dirs.remove(d)
                continue

            # 3-2. 기존 '날짜 최적화' 로직
            try:
                dir_date = datetime.datetime.strptime(d, '%Y%m%d').date()
                if dir_date < cutoff_date:
                    print(f"  [최적화] 오래된 날짜 폴더 제외: {current_root_path / d}")
                    dirs.remove(d)
            except ValueError:
                pass

        # --- 4. 파일 처리 로직 (날짜 폴더 '일괄 처리') ---
        is_date_folder = False
        try:
            current_dir_date = datetime.datetime.strptime(current_root_path.name, '%Y%m%d').date()
            if current_dir_date >= cutoff_date:
                is_date_folder = True
        except ValueError:
            pass

        if is_date_folder:
            #
            #
            for f in files:
                source_file = current_root_path / f
                # [수정됨] 허용 확장자 필터링
                if allowed_ext_set and (source_file.suffix.lower() not in allowed_ext_set):
                    continue  #

                relative_path = source_file.relative_to(source_dir)
                target_file = Path(target_dir) / relative_path

                # 0바이트 파일 생성 전 디렉터리 먼저 생성
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # 확장자 제외 이름이 이미 존재하는지 확인
                if not check_stem_exists(target_file):
                    target_file.touch()
                # else:
                #   print(f"  [스킵] 이미 존재: {target_file.stem}")

            continue  #

        # --- 5. 일반 파일 검사 (날짜 폴더가 아니거나, 최상위 폴더인 경우) ---
        for f in files:
            source_file = current_root_path / f

            # [수정됨] 허용 확장자 필터링
            if allowed_ext_set and (source_file.suffix.lower() not in allowed_ext_set):
                continue  #

            try:
                # mtime_stamp = os.path.getmtime(source_file)
                # mtime_dt = datetime.datetime.fromtimestamp(mtime_stamp)

                # 수정 시간이 기준 시간보다 최신이라면
                # if mtime_dt >= cutoff_dt:
                relative_path = source_file.relative_to(source_dir)
                target_file = Path(target_dir) / relative_path

                # 0바이트 파일 생성 전 디렉터리 먼저 생성
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # 확장자 제외 이름이 이미 존재하는지 확인
                if not check_stem_exists(target_file):
                    target_file.touch()
                # else:
                #   print(f"  [스킵] 이미 존재: {target_file.stem}")

            except FileNotFoundError:
                print(f"  [경고] 파일을 찾는 중 오류 발생: {source_file}")
                pass
            except OSError as e:
                #
                print(f"  [OS 오류] {source_file} 접근 중 오류: {e}")
            except Exception as e:
                print(f"  [알 수 없는 오류] {source_file} 처리 중 오류: {e}")

    print("--- 작업 완료 ---")


# # --- 함수 사용 예시 ---
# source_path = r"\\npsmain.mbcnps.com\ROOT\MASTER"
# target_path = r"C:\Users\gemisoadmin\Desktop\새폴더"
# days_to_scan = 80
# folders_to_skip = ["ProjectShare", "ShareFolder", ".temp"]
# ext_list = ['.mxf', '.wav', '.mov','.MXF', '.WAV', '.MOV']
#
#
# create_optimized_stubs(source_path, target_path, days_to_scan, folders_to_skip,ext_list)