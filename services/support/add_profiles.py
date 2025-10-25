import os
import sys

from services.support.path_config import get_profiles_file_path

def add_specific_target_profiles():
    if len(sys.argv) < 3:
        print("Usage: python add_profiles.py <startup_name> <profile1> [profile2 ...]")
        return

    startup_name = sys.argv[1].strip()
    
    if not startup_name:
        print("Startup name cannot be empty. Exiting.")
        return

    profiles = [f"https://x.com/{profile.strip()}" for profile in sys.argv[2:] if profile.strip()]
    
    if not profiles:
        print("No profiles provided. Exiting.")
        return

    profiles_file_path = get_profiles_file_path()

    try:
        with open(profiles_file_path, 'r') as f:
            content = f.readlines()

        insert_point_found = False
        new_profiles_section = []
        in_specific_target_profiles = False
        indentation = "    "
        
        for i, line in enumerate(content):
            if "SPECIFIC_TARGET_PROFILES = {" in line:
                insert_point_found = True
                new_profiles_section.append(line)
                closing_brace_index = -1
                for j in range(i + 1, len(content)):
                    if content[j].strip() == '}':
                        closing_brace_index = j
                        break

                if closing_brace_index != -1:
                    for k in range(i + 1, closing_brace_index):
                        new_profiles_section.append(content[k])
                    
                    if closing_brace_index > i + 1:
                        last_existing_line = content[closing_brace_index - 1].rstrip()
                        if last_existing_line and not last_existing_line.endswith(','):
                            new_profiles_section[-1] = last_existing_line + ',\n'
                    
                    new_profiles_section.append(indentation + f'"{startup_name}": [')
                    new_profiles_section.append('\n')
                    for profile in profiles:
                        new_profiles_section.append(indentation + indentation + f'"{profile}",')
                        new_profiles_section.append('\n')
                    new_profiles_section.append(indentation + '],')
                    new_profiles_section.append('\n')
                    new_profiles_section.extend(content[closing_brace_index:])
                    break
                else:
                    print("Could not find closing brace for 'SPECIFIC_TARGET_PROFILES'.")
                    return
            else:
                new_profiles_section.append(line)

        if not insert_point_found:
            print("Could not find 'SPECIFIC_TARGET_PROFILES' dictionary in profiles.py. Please ensure it exists.")
            return

        with open(profiles_file_path, 'w') as f:
            f.writelines(new_profiles_section)
        
        print(f"Successfully added '{startup_name}' with profiles to profiles.py")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    add_specific_target_profiles()
