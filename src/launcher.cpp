#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>
#include <vector>
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR arguments, int) {
    std::vector<wchar_t> buffer(32768);
    const DWORD size=GetModuleFileNameW(nullptr,buffer.data(),static_cast<DWORD>(buffer.size()));
    if(size==0 || size>=buffer.size()) return 1;
    const std::wstring own(buffer.data(),size);
    const auto split=own.find_last_of(L"\\/");
    const std::wstring root=own.substr(0,split);
    const std::wstring program=root+L"\\app\\BeautyPlayerV060.exe";
    std::wstring command=L"\""+program+L"\" "+arguments;
    STARTUPINFOW startup{}; startup.cb=sizeof(startup);
    PROCESS_INFORMATION process{};
    if(!CreateProcessW(program.c_str(),command.data(),nullptr,nullptr,FALSE,0,nullptr,root.c_str(),&startup,&process)) {
        MessageBoxW(nullptr,L"无法启动映澈。请完整解压文件夹，保留 app 和 models 目录。",L"映澈",MB_OK|MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread); CloseHandle(process.hProcess);
    return 0;
}
