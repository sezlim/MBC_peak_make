import os
import shutil
# import time
from pathlib import Path
import part1_ui
import part2_sync
import part3_import_upload
import config



#####################################################################
## 글로별 번수 정의




#####################################################################
def clear_folder_contents(path: str) -> bool:
    """
    주어진 경로의 폴더 내부 내용물(파일 및 하위 폴더)을 모두 삭제하고,
    최상위 폴더 자체는 유지합니다.

    Args:
        path (str): 내용을 비울 폴더의 경로.

    Returns:
        bool: 작업 성공 여부.
    """
    root_p = Path(path)

    if not root_p.is_dir():
        print(f"❌ 오류: 유효한 폴더 경로가 아닙니다: {path}")
        return False

    try:
        # 폴더 내의 모든 항목을 순회하며 삭제
        for item in root_p.iterdir():
            if item.is_dir():
                # 하위 폴더는 rmtree로 재귀적 삭제
                shutil.rmtree(item)
            else:
                # 파일은 unlink로 삭제
                item.unlink()

        print(f"✅ 폴더 내부 내용물 삭제 완료: {path}")
        return True
    except Exception as e:
        print(f"❌ 오류: 폴더 내부 내용 삭제 실패. 사유: {e}")
        return False




def find_premiere_startup_folders() -> list[Path]:
    """
    'C:\Program Files\Adobe' 경로 아래에서 이름에 'Adobe Premiere Pro'를 포함하는 폴더 내의
    모든 'Scripts\Startup' 폴더를 찾아 전체 경로를 반환합니다. (대소문자/띄어쓰기 무시)

    Returns:
        List[Path]: 찾은 모든 Scripts\Startup 폴더의 Path 객체 리스트.
    """

    # 기본 검색 시작 경로 정의
    base_path = Path(r"C:\Program Files\Adobe")
    target_subdir_parts = ('Scripts', 'Startup')  # 찾을 하위 폴더 이름 리스트
    target_app_name = "adobepremierepro"  # 검색을 한정할 이름 (소문자로 통일)
    found_paths: list[Path] = []

    # print(f"🔍 검색 시작 경로: {base_path}")
    # print(f"🎯 찾을 하위 폴더: \\{'\\'.join(target_subdir_parts)}")
    # print(f"✅ 폴더 이름 포함 조건: '{target_app_name}' (대소문자/띄어쓰기 무시)")

    if not base_path.is_dir():
        print(f"❌ 오류: 기본 경로를 찾을 수 없거나 접근할 수 없습니다: {base_path}")
        return []

    # rglob을 사용하되, 검색 범위를 'Adobe\*' 아래의 모든 폴더로 한정
    # 첫 번째 레벨 하위 폴더(예: Adobe Premiere Pro 2024, Adobe Photoshop 2024)를 찾습니다.
    # Adobe 폴더 바로 아래의 모든 폴더만 탐색
    for app_dir in base_path.iterdir():
        if app_dir.is_dir():

            # 폴더 이름에서 띄어쓰기를 제거하고 소문자로 변환
            normalized_name = app_dir.name.replace(' ', '').lower()

            # 1차 필터링: 폴더 이름이 'adobepremierepro'를 포함하는지 확인
            if target_app_name in normalized_name:

                # 2차 필터링: 해당 폴더 내에서 Scripts/Startup 경로를 찾음
                startup_path = app_dir / 'Scripts' / 'Startup'

                if startup_path.is_dir():
                    found_paths.append(startup_path)
                    print(f"  [발견] {startup_path}")
                # else:
                # print(f"  [스킵] Scripts\\Startup 폴더가 존재하지 않음: {app_dir.name}")

            # else:
            # print(f"  [제외] 이름 불일치: {app_dir.name}")

    if not found_paths:
        print("\n⚠️ 조건에 맞는 Scripts\\Startup 폴더를 찾을 수 없습니다.")

    return found_paths










if __name__ == "__main__":

    check_premiere_already_open = part1_ui.check_and_prompt_premiere_shutdown()

    if check_premiere_already_open == False:
        print("종료합니다.")
        exit(0)


    config.update_cache_path(config.nas_cache_path,config.nas_cache_path,"25.0")
    ## 레지스토리로 경로 변경


    watch_folder_path = config.create_folder_in_exe_dir("watch")
    Pro_Prefs_path = config.find_file_in_executable_subdirs("Adobe Premiere Pro Prefs")
    command_txt_path = config.find_file_in_executable_subdirs("command.txt")
    startup_jsx_path = config.find_file_in_executable_subdirs("startup_jsx.jsx")
    start_proj_path = config.find_file_in_executable_subdirs("startup.prproj")
    # for_peak_out_file_list = []
    # for i in range(1,5):
    #     for_peak_out_file_list.append(config.find_file_in_executable_subdirs(f"for_peak_out_{i}.wav"))

    list_of_config = config.find_files_in_documents_pathlib("Adobe Premiere Pro Prefs")

    for path in list_of_config:
        try:
            shutil.copy2(Pro_Prefs_path, path)
            print("복사 완료입니다.")
        except Exception as e:
            # pass 대신, 어떤 오류가 났는지 *반드시* 확인해야 합니다.
            print(f"[실패] {path} 덮어쓰기 실패 (오류: {e})")
            print("  (팁: Premiere Pro가 실행 중이라면 종료하고 다시 시도하세요.)")



    shutil.copy2(command_txt_path,watch_folder_path)
    shutil.copy2(startup_jsx_path,watch_folder_path)
    shutil.copy2(start_proj_path,watch_folder_path)


    command_txt_path = os.path.join(watch_folder_path,os.path.basename(command_txt_path))
    startup_jsx_path = os.path.join(watch_folder_path,os.path.basename(startup_jsx_path))
    startup_proj_path = os.path.join(watch_folder_path,os.path.basename(start_proj_path))


    config.watch_folder_path = watch_folder_path
    config.startup_proj_path = startup_proj_path
    config.startup_jsx_path= startup_jsx_path
    config.command_txt_path =command_txt_path


    config.update_jsx_paths(startup_jsx_path, watch_folder_path)



    premiere_startup_path = find_premiere_startup_folders()

    print(f"프리미어프로 시작 스크립트 저장소 {premiere_startup_path}")
    for path in premiere_startup_path:
        shutil.copy2(startup_jsx_path,path)
    ### 이렇게 해야 버전 상관없이 실행 가능

    print("준비 완료 됐습니다.")

    part1_ui.ui()