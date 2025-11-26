import os

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

    return found_paths[0]


# print(find_files_with_phrase("C:\Adobe_Cache",".mcdb","PGM02-Clip0001-308770.mxf</OriginalPath>"))