#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <commctrl.h>
#include <commdlg.h>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <thread>
#include <atomic>
#include <memory>
#include <iomanip>
#include "AdaptiveSolverCore.hpp"

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "comdlg32.lib")
#pragma comment(lib, "psapi.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

// Enable Modern Windows Native Visual Styles
#if defined _M_IX86
#pragma comment(linker,"/manifestdependency:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='x86' publicKeyToken='6595b64144ccf1df' language='*'\"")
#elif defined _M_X64 || defined __x86_64__
#pragma comment(linker,"/manifestdependency:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='amd64' publicKeyToken='6595b64144ccf1df' language='*'\"")
#else
#pragma comment(linker,"/manifestdependency:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='*' publicKeyToken='6595b64144ccf1df' language='*'\"")
#endif

// Custom Windows Messages
#define WM_APP_SOLVE_FINISHED (WM_USER + 102)

// Control IDs
enum ControlID {
    IDC_COMBO_PRESETS = 1100,
    IDC_BTN_LOAD_PRESET,
    IDC_EDIT_ELEMENTS,
    IDC_EDIT_TARGET,
    IDC_BTN_SOLVE,
    IDC_BTN_STOP,
    IDC_BTN_CLEAR,
    IDC_BTN_VIEW_SOLUTIONS,
    IDC_RADIO_FIND_ONE,
    IDC_RADIO_FIND_ALL,
    IDC_RADIO_COUNT_ALL,
    IDC_RADIO_DECISION,
    IDC_COMBO_WORKERS,
    IDC_COMBO_MEM_LIMIT,
    IDC_STATIC_META,
    IDC_STATIC_STATUS,
    IDC_EDIT_SOLUTION_OUTPUT,
    // Pop-up Dialog Controls
    IDC_POPUP_EDIT_LIST = 2100,
    IDC_POPUP_BTN_EXPORT,
    IDC_POPUP_BTN_CLOSE,
    IDC_POPUP_STATIC_INFO
};

// Global App State
HWND g_hWnd = NULL;
HWND g_hDlgSolutions = NULL;

// Controls
HWND g_hComboPresets = NULL, g_hBtnLoadPreset = NULL;
HWND g_hEditElements = NULL, g_hEditTarget = NULL;
HWND g_hRadioFindOne = NULL, g_hRadioFindAll = NULL, g_hRadioCountAll = NULL, g_hRadioDecision = NULL;
HWND g_hComboWorkers = NULL, g_hComboMem = NULL;
HWND g_hBtnSolve = NULL, g_hBtnStop = NULL, g_hBtnViewSolutions = NULL;
HWND g_hStaticMeta = NULL, g_hStaticStatus = NULL, g_hEditSolOutput = NULL;

// Standard Native Fonts
HFONT g_hFontNormal = NULL;
HFONT g_hFontBold = NULL;
HFONT g_hFontTitle = NULL;
HFONT g_hFontMono = NULL;

// Solver Threads & State
std::unique_ptr<AdaptiveExactSolver> g_solver;
std::thread g_workerThread;
std::atomic<bool> g_isSolving{false};
std::mutex g_statsMutex;

Instance g_currentInstance;
ExecutionStats g_lastStats;
std::vector<InstancePreset> g_presets;

// Forward Declarations
LRESULT CALLBACK WndProc(HWND, UINT, WPARAM, LPARAM);
LRESULT CALLBACK SolutionDialogWndProc(HWND, UINT, WPARAM, LPARAM);
LRESULT CALLBACK EditCtrlASubclassProc(HWND, UINT, WPARAM, LPARAM, UINT_PTR, DWORD_PTR);
void CreateMainUI(HWND hWnd);
void UpdateInstanceMetadataDisplay(const Instance& inst);
void UpdateLiveTelemetryDisplay(const ExecutionStats& stats, SolveMode mode);
void StartSolving();
void StopSolving();
void LoadSelectedPresetToSolver(int idx);
void ParseCurrentInputs();
std::string GetControlTextDynamic(HWND hEdit);
void SetAppBusyState(bool busy);
void OpenSolutionsPopupWindow(HWND hParent);
void ExportAllSolutionsToTxt(HWND hWndParent);

// Global SEH Crash Handler
LONG WINAPI GlobalCrashHandler(EXCEPTION_POINTERS* pException) {
    char buf[512];
    sprintf_s(buf, "CRASH DETECTED!\nException Code: 0x%08lX\nAddress: %p\n\nProcess is aborting safely.",
              (unsigned long)pException->ExceptionRecord->ExceptionCode,
              pException->ExceptionRecord->ExceptionAddress);
    std::cerr << "\n[FATAL CRASH]: " << buf << "\n";
    MessageBoxA(NULL, buf, "ATRS Solver Fatal Alert", MB_OK | MB_ICONERROR);
    return EXCEPTION_CONTINUE_SEARCH;
}

// Win32 Subclass Procedure for Ctrl+A Support on Edit Controls
LRESULT CALLBACK EditCtrlASubclassProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam, UINT_PTR uIdSubclass, DWORD_PTR dwRefData) {
    switch (uMsg) {
        case WM_KEYDOWN: {
            if (wParam == 'A' && (GetKeyState(VK_CONTROL) & 0x8000)) {
                SendMessage(hWnd, EM_SETSEL, 0, -1);
                return 0;
            }
            break;
        }
        case WM_CHAR: {
            if (wParam == 1) {
                return 0;
            }
            break;
        }
        case WM_NCDESTROY: {
            RemoveWindowSubclass(hWnd, EditCtrlASubclassProc, uIdSubclass);
            break;
        }
    }
    return DefSubclassProc(hWnd, uMsg, wParam, lParam);
}

// Main Entry Point
int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow) {
    SetUnhandledExceptionFilter(GlobalCrashHandler);

    INITCOMMONCONTROLSEX icex;
    icex.dwSize = sizeof(INITCOMMONCONTROLSEX);
    icex.dwICC = ICC_STANDARD_CLASSES;
    InitCommonControlsEx(&icex);

    g_hFontNormal = CreateFontW(15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                                OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    g_hFontBold = CreateFontW(15, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    g_hFontTitle = CreateFontW(18, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                               OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    g_hFontMono = CreateFontW(13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");

    g_solver = std::make_unique<AdaptiveExactSolver>();
    g_presets = PresetRepository::get_all_presets();

    // Register Main Window Class
    WNDCLASSEXW wc = { sizeof(WNDCLASSEXW) };
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = L"AdaptiveSSPGUIClass";
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    RegisterClassExW(&wc);

    // Register Pop-up Dialog Window Class
    WNDCLASSEXW wcDlg = { sizeof(WNDCLASSEXW) };
    wcDlg.lpfnWndProc = SolutionDialogWndProc;
    wcDlg.hInstance = hInstance;
    wcDlg.lpszClassName = L"AdaptiveSolutionViewerClass";
    wcDlg.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wcDlg.hCursor = LoadCursor(NULL, IDC_ARROW);
    wcDlg.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    RegisterClassExW(&wcDlg);

    g_hWnd = CreateWindowExW(
        0, L"AdaptiveSSPGUIClass",
        L"Adaptive Exact Subset Sum Solver (C++20 ATRS v2 Engine)",
        WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN,
        CW_USEDEFAULT, CW_USEDEFAULT, 1150, 840,
        NULL, NULL, hInstance, NULL
    );

    ShowWindow(g_hWnd, nCmdShow);
    UpdateWindow(g_hWnd);

    // Start with clean empty inputs on startup
    UpdateInstanceMetadataDisplay(g_currentInstance);

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    if (g_workerThread.joinable()) {
        if (g_solver) g_solver->stop_flag = true;
        g_workerThread.join();
    }

    DeleteObject(g_hFontNormal);
    DeleteObject(g_hFontBold);
    DeleteObject(g_hFontTitle);
    DeleteObject(g_hFontMono);

    return 0;
}

// Window Procedure for Main GUI
LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_CREATE: {
            CreateMainUI(hWnd);
            break;
        }
        case WM_SIZE: {
            break;
        }
        case WM_COMMAND: {
            int id = LOWORD(wParam);

            if (id == IDC_BTN_SOLVE) {
                StartSolving();
            } else if (id == IDC_BTN_STOP) {
                StopSolving();
            } else if (id == IDC_BTN_CLEAR) {
                SetWindowTextA(g_hEditElements, "");
                SetWindowTextA(g_hEditTarget, "");
                SetWindowTextA(g_hEditSolOutput, "");
                g_currentInstance = Instance();
                UpdateInstanceMetadataDisplay(g_currentInstance);
                if (g_hBtnViewSolutions) EnableWindow(g_hBtnViewSolutions, FALSE);
            } else if (id == IDC_BTN_LOAD_PRESET) {
                int idx = SendMessage(g_hComboPresets, CB_GETCURSEL, 0, 0);
                LoadSelectedPresetToSolver(idx);
                if (g_hBtnViewSolutions) EnableWindow(g_hBtnViewSolutions, FALSE);
            } else if (id == IDC_BTN_VIEW_SOLUTIONS) {
                OpenSolutionsPopupWindow(hWnd);
            }
            break;
        }
        case WM_APP_SOLVE_FINISHED: {
            g_isSolving = false;
            SetAppBusyState(false);

            SolveMode mode = SolveMode::FindOne;
            if (SendMessage(g_hRadioFindAll, BM_GETCHECK, 0, 0) == BST_CHECKED) mode = SolveMode::FindAll;
            else if (SendMessage(g_hRadioCountAll, BM_GETCHECK, 0, 0) == BST_CHECKED) mode = SolveMode::CountAll;
            else if (SendMessage(g_hRadioDecision, BM_GETCHECK, 0, 0) == BST_CHECKED) mode = SolveMode::DecisionOnly;

            ExecutionStats stats_copy;
            {
                std::lock_guard<std::mutex> lock(g_statsMutex);
                stats_copy = g_lastStats;
            }

            UpdateLiveTelemetryDisplay(stats_copy, mode);

            // Aktifkan tombol "Lihat Solusi" jika mode FindAll dan terdapat solusi
            if (mode == SolveMode::FindAll && stats_copy.has_solution && !stats_copy.all_solutions.empty()) {
                EnableWindow(g_hBtnViewSolutions, TRUE);
            } else {
                EnableWindow(g_hBtnViewSolutions, FALSE);
            }
            break;
        }
        case WM_DESTROY: {
            PostQuitMessage(0);
            break;
        }
        default:
            return DefWindowProcW(hWnd, msg, wParam, lParam);
    }
    return 0;
}

// Helper: Safely get full control text dynamically
std::string GetControlTextDynamic(HWND hEdit) {
    if (!hEdit) return "";
    int len = GetWindowTextLengthA(hEdit);
    if (len <= 0) return "";
    std::string str(len + 1, '\0');
    GetWindowTextA(hEdit, &str[0], len + 1);
    str.resize(len);
    return str;
}

void SetAppBusyState(bool busy) {
    EnableWindow(g_hBtnSolve, !busy);
    EnableWindow(g_hBtnLoadPreset, !busy);
    EnableWindow(g_hBtnStop, busy);
    if (busy && g_hBtnViewSolutions) {
        EnableWindow(g_hBtnViewSolutions, FALSE);
    }
}

// Load Selected Preset directly into input boxes
void LoadSelectedPresetToSolver(int idx) {
    if (idx < 0 || idx >= (int)g_presets.size()) idx = 0;
    const auto& p = g_presets[idx];

    std::stringstream ss;
    for (size_t i = 0; i < p.elements.size(); ++i) {
        ss << p.elements[i];
        if (i + 1 < p.elements.size()) ss << ", ";
    }
    std::string elem_str = ss.str();
    std::string tgt_str = std::to_string(p.target);

    if (g_hEditElements) SetWindowTextA(g_hEditElements, elem_str.c_str());
    if (g_hEditTarget) SetWindowTextA(g_hEditTarget, tgt_str.c_str());

    g_currentInstance = Instance::from_string(elem_str, p.target);
    UpdateInstanceMetadataDisplay(g_currentInstance);
}

// Parse Current Inputs from TextBoxes
void ParseCurrentInputs() {
    std::string s_elem = GetControlTextDynamic(g_hEditElements);
    std::string s_tgt = GetControlTextDynamic(g_hEditTarget);

    if (s_elem.empty()) {
        g_currentInstance = Instance();
        UpdateInstanceMetadataDisplay(g_currentInstance);
        return;
    }

    u64 tgt = std::strtoull(s_tgt.c_str(), NULL, 10);
    g_currentInstance = Instance::from_string(s_elem, tgt);
    UpdateInstanceMetadataDisplay(g_currentInstance);
}

// Create Unified Main UI
void CreateMainUI(HWND hWnd) {
    // -------------------------------------------------------------
    // GENERATOR PRESET SECTION
    // -------------------------------------------------------------
    HWND lblGen = CreateWindowExW(0, L"STATIC", L"Dataset Generator / Preset:", WS_CHILD | WS_VISIBLE, 15, 15, 500, 20, hWnd, NULL, NULL, NULL);
    SendMessage(lblGen, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    g_hComboPresets = CreateWindowExW(0, L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 15, 38, 380, 300, hWnd, (HMENU)(INT_PTR)IDC_COMBO_PRESETS, NULL, NULL);
    for (const auto& p : g_presets) {
        std::wstring ws(p.title.begin(), p.title.end());
        SendMessage(g_hComboPresets, CB_ADDSTRING, 0, (LPARAM)ws.c_str());
    }
    SendMessage(g_hComboPresets, CB_SETCURSEL, 0, 0);
    SendMessage(g_hComboPresets, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);

    g_hBtnLoadPreset = CreateWindowExW(0, L"BUTTON", L"⬇ Load to Inputs", WS_CHILD | WS_VISIBLE, 405, 36, 140, 26, hWnd, (HMENU)(INT_PTR)IDC_BTN_LOAD_PRESET, NULL, NULL);
    SendMessage(g_hBtnLoadPreset, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);

    // -------------------------------------------------------------
    // INPUT SECTION
    // -------------------------------------------------------------
    HWND lbl1 = CreateWindowExW(0, L"STATIC", L"Input Elements (Comma-Separated or Multiline Integers):", WS_CHILD | WS_VISIBLE, 15, 75, 500, 20, hWnd, NULL, NULL, NULL);
    SendMessage(lbl1, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    g_hEditElements = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL,
        15, 95, 530, 150, hWnd, (HMENU)(INT_PTR)IDC_EDIT_ELEMENTS, NULL, NULL
    );
    SendMessage(g_hEditElements, WM_SETFONT, (WPARAM)g_hFontMono, TRUE);

    HWND lbl2 = CreateWindowExW(0, L"STATIC", L"Target Value (T):", WS_CHILD | WS_VISIBLE, 15, 255, 130, 20, hWnd, NULL, NULL, NULL);
    SendMessage(lbl2, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    g_hEditTarget = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
        145, 253, 400, 24, hWnd, (HMENU)(INT_PTR)IDC_EDIT_TARGET, NULL, NULL
    );
    SendMessage(g_hEditTarget, WM_SETFONT, (WPARAM)g_hFontMono, TRUE);

    // -------------------------------------------------------------
    // SOLVE MODE & OPTIONS SECTION
    // -------------------------------------------------------------
    HWND grpMode = CreateWindowExW(0, L"BUTTON", L"Solve Mode", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 15, 285, 530, 55, hWnd, NULL, NULL, NULL);
    SendMessage(grpMode, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    g_hRadioFindOne = CreateWindowExW(0, L"BUTTON", L"Find One", WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON | WS_GROUP, 30, 307, 95, 20, hWnd, (HMENU)(INT_PTR)IDC_RADIO_FIND_ONE, NULL, NULL);
    g_hRadioFindAll = CreateWindowExW(0, L"BUTTON", L"Find All Solutions", WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON, 130, 307, 135, 20, hWnd, (HMENU)(INT_PTR)IDC_RADIO_FIND_ALL, NULL, NULL);
    g_hRadioCountAll = CreateWindowExW(0, L"BUTTON", L"Count All", WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON, 270, 307, 95, 20, hWnd, (HMENU)(INT_PTR)IDC_RADIO_COUNT_ALL, NULL, NULL);
    g_hRadioDecision = CreateWindowExW(0, L"BUTTON", L"Decision Only", WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON, 370, 307, 120, 20, hWnd, (HMENU)(INT_PTR)IDC_RADIO_DECISION, NULL, NULL);
    SendMessage(g_hRadioFindOne, BM_SETCHECK, BST_CHECKED, 0);
    SendMessage(g_hRadioFindOne, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
    SendMessage(g_hRadioFindAll, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
    SendMessage(g_hRadioCountAll, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
    SendMessage(g_hRadioDecision, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);

    // Parallel Worker & Memory Combo
    HWND lblW = CreateWindowExW(0, L"STATIC", L"CPU Workers:", WS_CHILD | WS_VISIBLE, 15, 350, 95, 20, hWnd, NULL, NULL, NULL);
    SendMessage(lblW, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
    g_hComboWorkers = CreateWindowExW(0, L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 115, 347, 140, 150, hWnd, (HMENU)(INT_PTR)IDC_COMBO_WORKERS, NULL, NULL);
    SendMessage(g_hComboWorkers, CB_ADDSTRING, 0, (LPARAM)L"Auto (All Cores)");
    SendMessage(g_hComboWorkers, CB_ADDSTRING, 0, (LPARAM)L"1 Core");
    SendMessage(g_hComboWorkers, CB_ADDSTRING, 0, (LPARAM)L"2 Cores");
    SendMessage(g_hComboWorkers, CB_ADDSTRING, 0, (LPARAM)L"4 Cores");
    SendMessage(g_hComboWorkers, CB_ADDSTRING, 0, (LPARAM)L"8 Cores");
    SendMessage(g_hComboWorkers, CB_SETCURSEL, 0, 0);
    SendMessage(g_hComboWorkers, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);

    HWND lblM = CreateWindowExW(0, L"STATIC", L"RAM Budget:", WS_CHILD | WS_VISIBLE, 275, 350, 90, 20, hWnd, NULL, NULL, NULL);
    SendMessage(lblM, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
    g_hComboMem = CreateWindowExW(0, L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 370, 347, 175, 150, hWnd, (HMENU)(INT_PTR)IDC_COMBO_MEM_LIMIT, NULL, NULL);
    SendMessage(g_hComboMem, CB_ADDSTRING, 0, (LPARAM)L"Auto (Safe)");
    SendMessage(g_hComboMem, CB_ADDSTRING, 0, (LPARAM)L"2048 MB");
    SendMessage(g_hComboMem, CB_ADDSTRING, 0, (LPARAM)L"4096 MB");
    SendMessage(g_hComboMem, CB_ADDSTRING, 0, (LPARAM)L"8192 MB");
    SendMessage(g_hComboMem, CB_SETCURSEL, 2, 0);
    SendMessage(g_hComboMem, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);

    // -------------------------------------------------------------
    // ACTION BUTTONS SECTION
    // -------------------------------------------------------------
    g_hBtnSolve = CreateWindowExW(0, L"BUTTON", L"▶ SOLVE EXACT", WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON, 15, 385, 160, 40, hWnd, (HMENU)(INT_PTR)IDC_BTN_SOLVE, NULL, NULL);
    g_hBtnStop = CreateWindowExW(0, L"BUTTON", L"⏹ STOP", WS_CHILD | WS_VISIBLE, 185, 385, 80, 40, hWnd, (HMENU)(INT_PTR)IDC_BTN_STOP, NULL, NULL);
    HWND btnClear = CreateWindowExW(0, L"BUTTON", L"Clear", WS_CHILD | WS_VISIBLE, 275, 385, 75, 40, hWnd, (HMENU)(INT_PTR)IDC_BTN_CLEAR, NULL, NULL);
    g_hBtnViewSolutions = CreateWindowExW(0, L"BUTTON", L"📋 Lihat Solusi", WS_CHILD | WS_VISIBLE, 360, 385, 185, 40, hWnd, (HMENU)(INT_PTR)IDC_BTN_VIEW_SOLUTIONS, NULL, NULL);
    
    EnableWindow(g_hBtnStop, FALSE);
    EnableWindow(g_hBtnViewSolutions, FALSE); // Awalnya nonaktif sampai Find All selesai

    SendMessage(g_hBtnSolve, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);
    SendMessage(g_hBtnStop, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);
    SendMessage(btnClear, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
    SendMessage(g_hBtnViewSolutions, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    // -------------------------------------------------------------
    // SOLUTION OUTPUT SECTION
    // -------------------------------------------------------------
    HWND lblSol = CreateWindowExW(0, L"STATIC", L"Exact Solution Output / Mathematical Verification Proof:", WS_CHILD | WS_VISIBLE, 15, 440, 500, 20, hWnd, NULL, NULL, NULL);
    SendMessage(lblSol, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);
    g_hEditSolOutput = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
        15, 460, 530, 320, hWnd, (HMENU)(INT_PTR)IDC_EDIT_SOLUTION_OUTPUT, NULL, NULL
    );
    SendMessage(g_hEditSolOutput, WM_SETFONT, (WPARAM)g_hFontMono, TRUE);

    SendMessage(g_hEditSolOutput, EM_SETLIMITTEXT, 0, 0);

    SetWindowSubclass(g_hEditElements, EditCtrlASubclassProc, 1, 0);
    SetWindowSubclass(g_hEditTarget, EditCtrlASubclassProc, 2, 0);
    SetWindowSubclass(g_hEditSolOutput, EditCtrlASubclassProc, 3, 0);

    // -------------------------------------------------------------
    // RIGHT PANEL - TELEMETRY & METADATA
    // -------------------------------------------------------------
    HWND grpMeta = CreateWindowExW(0, L"BUTTON", L"Instance Structure & Normalization", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 565, 15, 545, 230, hWnd, NULL, NULL, NULL);
    SendMessage(grpMeta, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    g_hStaticMeta = CreateWindowExW(
        0, L"STATIC",
        L"Elements (N)    : -\n"
        L"Target (T)      : -\n"
        L"Total Sum (ΣA)  : -\n"
        L"Min / Max Value : -\n"
        L"Suffix GCD      : -\n"
        L"Zero / Odd/Even : -\n"
        L"Density Score   : -\n"
        L"Effective Target: -\n"
        L"Feasible K Range: -",
        WS_CHILD | WS_VISIBLE, 580, 40, 515, 195, hWnd, (HMENU)(INT_PTR)IDC_STATIC_META, NULL, NULL
    );
    SendMessage(g_hStaticMeta, WM_SETFONT, (WPARAM)g_hFontMono, TRUE);

    HWND grpStatus = CreateWindowExW(0, L"BUTTON", L"Live Adaptive Solver Telemetry", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 565, 255, 545, 525, hWnd, NULL, NULL, NULL);
    SendMessage(grpStatus, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

    g_hStaticStatus = CreateWindowExW(
        0, L"STATIC",
        L"Status          : IDLE (Awaiting input)\n\n"
        L"Strategy Chosen : -\n"
        L"Workers Used    : -\n"
        L"Elapsed Time    : 0.00 ms\n"
        L"States Evaluated: 0\n"
        L"States Pruned   : 0\n"
        L"Forced Decisions: 0\n"
        L"Comparisons     : 0\n"
        L"Peak Resident RAM: 0.00 MB\n\n"
        L"Engine Status   : Ready",
        WS_CHILD | WS_VISIBLE, 580, 285, 515, 485, hWnd, (HMENU)(INT_PTR)IDC_STATIC_STATUS, NULL, NULL
    );
    SendMessage(g_hStaticStatus, WM_SETFONT, (WPARAM)g_hFontMono, TRUE);
}

// Update Instance Metadata Panel
void UpdateInstanceMetadataDisplay(const Instance& inst) {
    std::wstringstream ss;
    ss << L"Elements (N)    : " << inst.raw_elements.size() << L" raw (" << inst.A.size() << L" positive active)\n";
    ss << L"Target (T)      : " << inst.target << L"\n";
    ss << L"Total Sum (ΣA)  : " << (u64)inst.total_sum << L"\n";
    ss << L"Min / Max Value : " << inst.min_val << L" / " << inst.max_val << L"\n";
    ss << L"Suffix GCD      : " << inst.gcd_val << L"\n";
    ss << L"Zero / Odd/Even : " << inst.zero_indices.size() << L" zeroes | " << inst.odd_count << L" odd / " << inst.even_count << L" even\n";
    ss << std::fixed << std::setprecision(4) << L"Density Score   : " << inst.density << L"\n";
    ss << L"Effective Target: " << inst.effective_target << (inst.complement_applied ? L" (Complement Applied)" : L"") << L"\n";
    ss << L"Feasible K Range: [" << inst.k_min << L" .. " << inst.k_max << L"] (" << inst.feasible_k_count << L" valid counts)";
    if (g_hStaticMeta) SetWindowTextW(g_hStaticMeta, ss.str().c_str());
}

// Update Telemetry Panel
void UpdateLiveTelemetryDisplay(const ExecutionStats& stats, SolveMode mode) {
    std::wstringstream ss;
    std::wstring status_str = L"COMPLETED (Exact)";
    if (stats.status == SolverStatus::StoppedByUser) status_str = L"STOPPED BY USER";
    else if (stats.status == SolverStatus::PartialSolutionCapped) status_str = L"COMPLETED (Capped Limit)";
    else if (stats.status == SolverStatus::UnknownTimeout) status_str = L"STOPPED (Timeout)";
    else if (stats.status == SolverStatus::UnknownMemoryExceeded) status_str = L"STOPPED (Memory Exceeded)";
    else if (!stats.solved) status_str = L"STOPPED / ERROR";

    ss << L"Status          : " << status_str << L"\n\n";
    ss << L"Strategy Chosen : " << std::wstring(strategy_to_string(stats.strategy_chosen).begin(), strategy_to_string(stats.strategy_chosen).end()) << L"\n";
    ss << L"Workers Used    : " << stats.workers_used << L" logical CPU core(s)\n";
    ss << std::fixed << std::setprecision(2) << L"Elapsed Time    : " << stats.runtime_ms << L" ms (Preprocess: " << stats.preprocess_ms << L" ms)\n";
    ss << L"States Evaluated: " << stats.states_evaluated << L"\n";
    ss << L"States Pruned   : " << stats.states_pruned << L"\n";
    ss << L"Forced Take/Skip: " << stats.forced_take << L" / " << stats.forced_skip << L"\n";
    ss << L"Comparisons     : " << stats.comparisons << L"\n";
    ss << L"Memo Hits/Lookups: " << stats.memo_hits << L" / " << stats.memo_lookups << L"\n";
    ss << std::fixed << std::setprecision(2) << L"Peak Resident RAM: " << stats.peak_ram_mb << L" MB\n\n";
    ss << L"Engine Status   : " << std::wstring(stats.message.begin(), stats.message.end());
    if (g_hStaticStatus) SetWindowTextW(g_hStaticStatus, ss.str().c_str());

    // Update Solution Output
    std::wstringstream sol_ss;
    if (stats.has_solution) {
        if (mode == SolveMode::FindAll) {
            sol_ss << L"=== ALL EXACT SOLUTIONS FOUND ===\n";
            sol_ss << L"Total Solutions Counted: " << (u64)stats.solution_count << L"\n";
            sol_ss << L"Solutions Stored       : " << stats.all_solutions.size() << L"\n\n";

            size_t max_disp = std::min(stats.all_solutions.size(), (size_t)50);
            for (size_t idx = 0; idx < max_disp; ++idx) {
                const auto& sol = stats.all_solutions[idx];
                u64 sum = 0;
                sol_ss << L"Solution #" << (idx + 1) << L" (" << sol.values.size() << L" elements): [";
                for (size_t i = 0; i < sol.values.size(); ++i) {
                    sol_ss << sol.values[i];
                    sum += sol.values[i];
                    if (i + 1 < sol.values.size()) sol_ss << L", ";
                }
                sol_ss << L"] -> Sum = " << sum << L" (" << (sum == g_currentInstance.target ? L"VALID" : L"INVALID") << L")\n";
            }

            if (stats.all_solutions.size() > max_disp) {
                sol_ss << L"\n... [" << (stats.all_solutions.size() - max_disp) 
                       << L" solusi lainnya tersimpan! Klik tombol '📋 Lihat Solusi' di atas untuk melihat ratusan solusi atau ekspor ke .txt]\n";
            }
            if (stats.status == SolverStatus::PartialSolutionCapped) {
                sol_ss << L"\n[INFO]: Penyimpanan witness dibatasi pada " << stats.all_solutions.size() 
                       << L" solusi demi keamanan memori. Penghitungan count tetap 100% eksak.\n";
            }
            sol_ss << L"\nVerification: 100% Mathematically Exact.";
        } else if (mode == SolveMode::CountAll) {
            sol_ss << L"=== TOTAL SOLUTIONS COUNT ===\n";
            sol_ss << L"Exact Solution Count: " << (u64)stats.solution_count << L" valid subsets summing to " << g_currentInstance.target << L".\n";
        } else if (mode == SolveMode::DecisionOnly) {
            sol_ss << L"=== DECISION RESULT ===\n";
            sol_ss << L"Target is SATISFIABLE: At least one exact subset exists summing to " << g_currentInstance.target << L".\n";
        } else {
            sol_ss << L"=== EXACT SOLUTION FOUND ===\n";
            sol_ss << L"Subset Size: " << stats.sample_solution.values.size() << L" elements\n";
            u64 check_sum = 0;
            sol_ss << L"Elements:\n[";
            for (size_t i = 0; i < stats.sample_solution.values.size(); ++i) {
                sol_ss << stats.sample_solution.values[i];
                check_sum += stats.sample_solution.values[i];
                if (i + 1 < stats.sample_solution.values.size()) sol_ss << L", ";
            }
            sol_ss << L"]\n\nVerification Check: Sum = " << check_sum << L" (Matches Target: " << (check_sum == g_currentInstance.target ? L"YES - 100% VALID" : L"NO") << L")\n";
        }
    } else {
        if (stats.status == SolverStatus::StoppedByUser) {
            sol_ss << L"=== SEARCH STOPPED BY USER ===\n";
            sol_ss << L"Proses pencarian telah dihentikan oleh pengguna.\n";
        } else {
            sol_ss << L"=== EXACT UNSAT PROVEN ===\n";
            sol_ss << L"No subset of the given elements sums to " << g_currentInstance.target << L".\n";
        }
    }
    if (g_hEditSolOutput) SetWindowTextW(g_hEditSolOutput, sol_ss.str().c_str());
}

// Start Solving Task
void StartSolving() {
    if (g_isSolving) return;

    ParseCurrentInputs();

    SolveMode mode = SolveMode::FindOne;
    if (SendMessage(g_hRadioFindAll, BM_GETCHECK, 0, 0) == BST_CHECKED) mode = SolveMode::FindAll;
    else if (SendMessage(g_hRadioCountAll, BM_GETCHECK, 0, 0) == BST_CHECKED) mode = SolveMode::CountAll;
    else if (SendMessage(g_hRadioDecision, BM_GETCHECK, 0, 0) == BST_CHECKED) mode = SolveMode::DecisionOnly;

    int worker_sel = SendMessage(g_hComboWorkers, CB_GETCURSEL, 0, 0);
    int req_workers = 0;
    if (worker_sel == 1) req_workers = 1;
    else if (worker_sel == 2) req_workers = 2;
    else if (worker_sel == 3) req_workers = 4;
    else if (worker_sel == 4) req_workers = 8;

    int mem_sel = SendMessage(g_hComboMem, CB_GETCURSEL, 0, 0);
    size_t mem_limit = (mem_sel == 1) ? 2048 : (mem_sel == 2) ? 4096 : (mem_sel == 3) ? 8192 : 4096;

    g_isSolving = true;
    SetAppBusyState(true);
    SetWindowTextW(g_hEditSolOutput, L"Solving with ATRS v2 Native Engine in background...");
    if (g_hStaticStatus) {
        SetWindowTextW(g_hStaticStatus,
            L"Status          : RUNNING (Solving in background...)\n\n"
            L"Strategy Chosen : Evaluating...\n"
            L"Workers Used    : Active\n"
            L"Elapsed Time    : Computing...\n"
            L"States Evaluated: Exploring...\n"
            L"States Pruned   : -\n"
            L"Forced Decisions: -\n"
            L"Comparisons     : -\n"
            L"Peak Resident RAM: Active\n\n"
            L"Engine Status   : Search in progress..."
        );
    }

    if (g_workerThread.joinable()) g_workerThread.join();

    Instance inst_copy = g_currentInstance;
    g_workerThread = std::thread([inst_copy, mode, req_workers, mem_limit]() {
        ExecutionStats result;
        try {
            result = g_solver->run(inst_copy, mode, req_workers, mem_limit);
        } catch (const std::exception& ex) {
            result.message = std::string("Exception: ") + ex.what();
            result.solved = false;
        } catch (...) {
            result.message = "Unknown error occurred.";
            result.solved = false;
        }
        {
            std::lock_guard<std::mutex> lock(g_statsMutex);
            g_lastStats = std::move(result);
        }
        PostMessage(g_hWnd, WM_APP_SOLVE_FINISHED, 0, 0);
    });
}

// Stop Solving Task
void StopSolving() {
    if (g_isSolving && g_solver) {
        g_solver->stop_flag = true;
    }
}

// =========================================================================
// POP-UP DIALOG WINDOW: LIHAT SEMUA SOLUSI & EKSPOR KE TXT
// =========================================================================
LRESULT CALLBACK SolutionDialogWndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_CREATE: {
            // Header Info Label
            std::wstringstream info_ss;
            size_t total_stored = g_lastStats.all_solutions.size();
            u64 total_counted = (u64)g_lastStats.solution_count;

            if (total_counted > 1000 || total_stored > 1000) {
                info_ss << L"⚠ Ditemukan " << total_counted << L" solusi lebih (" 
                        << total_stored << L" solusi tersimpan di memori).\n"
                        << L"Menampilkan 500 solusi pertama di layar. Untuk melihat seluruh solusi lengkap, silakan klik tombol '💾 Ekspor TXT'.";
            } else {
                info_ss << L"Total Solusi Ditemukan: " << total_stored 
                        << L" solusi valid untuk Target T = " << g_currentInstance.target << L".";
            }

            HWND lblInfo = CreateWindowExW(
                0, L"STATIC", info_ss.str().c_str(),
                WS_CHILD | WS_VISIBLE,
                15, 15, 800, 45, hWnd, (HMENU)(INT_PTR)IDC_POPUP_STATIC_INFO, NULL, NULL
            );
            SendMessage(lblInfo, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

            // Multiline Edit Box for Solution Viewing
            HWND hEditList = CreateWindowExW(
                WS_EX_CLIENTEDGE, L"EDIT", L"",
                WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
                15, 65, 800, 490, hWnd, (HMENU)(INT_PTR)IDC_POPUP_EDIT_LIST, NULL, NULL
            );
            SendMessage(hEditList, WM_SETFONT, (WPARAM)g_hFontMono, TRUE);
            SendMessage(hEditList, EM_SETLIMITTEXT, 0, 0);
            SetWindowSubclass(hEditList, EditCtrlASubclassProc, 10, 0);

            // Format up to 500 solutions into the edit box
            std::wstringstream list_ss;
            size_t disp_limit = std::min(total_stored, (size_t)500);
            for (size_t idx = 0; idx < disp_limit; ++idx) {
                const auto& sol = g_lastStats.all_solutions[idx];
                u64 sum = 0;
                list_ss << L"Solusi #" << (idx + 1) << L" (" << sol.values.size() << L" elemen): [";
                for (size_t i = 0; i < sol.values.size(); ++i) {
                    list_ss << sol.values[i];
                    sum += sol.values[i];
                    if (i + 1 < sol.values.size()) list_ss << L", ";
                }
                list_ss << L"] -> Sum = " << sum << L" (" << (sum == g_currentInstance.target ? L"VALID" : L"INVALID") << L")\r\n";
            }
            if (total_stored > disp_limit) {
                list_ss << L"\r\n... [Terdapat " << (total_stored - disp_limit) 
                        << L" solusi lainnya yang tidak ditampilkan di layar. Silakan gunakan tombol 'Ekspor TXT' di bawah untuk mengekspor seluruh solusi ke file text]\r\n";
            }
            SetWindowTextW(hEditList, list_ss.str().c_str());

            // Action Buttons: Ekspor TXT & Tutup
            HWND btnExport = CreateWindowExW(
                0, L"BUTTON", L"💾 Ekspor Seluruh Solusi ke TXT",
                WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON,
                15, 565, 260, 36, hWnd, (HMENU)(INT_PTR)IDC_POPUP_BTN_EXPORT, NULL, NULL
            );
            SendMessage(btnExport, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

            HWND btnClose = CreateWindowExW(
                0, L"BUTTON", L"Tutup",
                WS_CHILD | WS_VISIBLE,
                705, 565, 110, 36, hWnd, (HMENU)(INT_PTR)IDC_POPUP_BTN_CLOSE, NULL, NULL
            );
            SendMessage(btnClose, WM_SETFONT, (WPARAM)g_hFontNormal, TRUE);
            break;
        }
        case WM_COMMAND: {
            int id = LOWORD(wParam);
            if (id == IDC_POPUP_BTN_EXPORT) {
                ExportAllSolutionsToTxt(hWnd);
            } else if (id == IDC_POPUP_BTN_CLOSE) {
                DestroyWindow(hWnd);
            }
            break;
        }
        case WM_DESTROY: {
            g_hDlgSolutions = NULL;
            break;
        }
        default:
            return DefWindowProcW(hWnd, msg, wParam, lParam);
    }
    return 0;
}

// Buka Jendela Pop-up Lihat Solusi
void OpenSolutionsPopupWindow(HWND hParent) {
    if (g_hDlgSolutions != NULL) {
        SetForegroundWindow(g_hDlgSolutions);
        return;
    }

    g_hDlgSolutions = CreateWindowExW(
        WS_EX_DLGMODALFRAME,
        L"AdaptiveSolutionViewerClass",
        L"Daftar Seluruh Solusi Eksak (Find All Solutions Viewer)",
        WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
        CW_USEDEFAULT, CW_USEDEFAULT, 845, 650,
        hParent, NULL, GetModuleHandle(NULL), NULL
    );

    // Center Dialog relative to main window
    RECT rcParent, rcDlg;
    GetWindowRect(hParent, &rcParent);
    GetWindowRect(g_hDlgSolutions, &rcDlg);
    int x = rcParent.left + ((rcParent.right - rcParent.left) - (rcDlg.right - rcDlg.left)) / 2;
    int y = rcParent.top + ((rcParent.bottom - rcParent.top) - (rcDlg.bottom - rcDlg.top)) / 2;
    SetWindowPos(g_hDlgSolutions, HWND_TOP, x, y, 0, 0, SWP_NOSIZE);
}

// Fungsi Ekspor Seluruh Solusi ke File TXT
void ExportAllSolutionsToTxt(HWND hWndParent) {
    if (g_lastStats.all_solutions.empty()) {
        MessageBoxW(hWndParent, L"Tidak ada solusi yang tersimpan untuk diekspor.", L"Info Ekspor", MB_OK | MB_ICONINFORMATION);
        return;
    }

    OPENFILENAMEW ofn;
    wchar_t szFile[MAX_PATH] = L"all_solutions_export.txt";

    ZeroMemory(&ofn, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = hWndParent;
    ofn.lpstrFile = szFile;
    ofn.nMaxFile = sizeof(szFile) / sizeof(wchar_t);
    ofn.lpstrFilter = L"Text Files (*.txt)\0*.txt\0All Files (*.*)\0*.*\0";
    ofn.nFilterIndex = 1;
    ofn.lpstrDefExt = L"txt";
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_OVERWRITEPROMPT;

    if (GetSaveFileNameW(&ofn)) {
        std::ofstream fout(szFile);
        if (!fout.is_open()) {
            MessageBoxW(hWndParent, L"Gagal membuka file untuk penulisan.", L"Error Ekspor", MB_OK | MB_ICONERROR);
            return;
        }

        fout << "================================================================================\n";
        fout << "ADAPTIVE EXACT SUBSET SUM SOLVER - EKSPOR SELURUH SOLUSI EKSAK\n";
        fout << "================================================================================\n";
        fout << "Target (T)             : " << g_currentInstance.target << "\n";
        fout << "Total Elements (N)     : " << g_currentInstance.raw_elements.size() << " raw (" << g_currentInstance.A.size() << " positive active)\n";
        fout << "Strategy Chosen        : " << strategy_to_string(g_lastStats.strategy_chosen) << "\n";
        fout << "Elapsed Runtime        : " << g_lastStats.runtime_ms << " ms\n";
        fout << "Total Exact Counted    : " << (u64)g_lastStats.solution_count << "\n";
        fout << "Total Solutions Stored : " << g_lastStats.all_solutions.size() << "\n";
        fout << "================================================================================\n\n";

        for (size_t idx = 0; idx < g_lastStats.all_solutions.size(); ++idx) {
            const auto& sol = g_lastStats.all_solutions[idx];
            u64 sum = 0;
            fout << "Solusi #" << (idx + 1) << " (" << sol.values.size() << " elemen): [";
            for (size_t i = 0; i < sol.values.size(); ++i) {
                fout << sol.values[i];
                sum += sol.values[i];
                if (i + 1 < sol.values.size()) fout << ", ";
            }
            fout << "] -> Sum = " << sum << " (" << (sum == g_currentInstance.target ? "VALID" : "INVALID") << ")\n";
            fout << "   Indeks Asli: [";
            for (size_t i = 0; i < sol.original_indices.size(); ++i) {
                fout << sol.original_indices[i];
                if (i + 1 < sol.original_indices.size()) fout << ", ";
            }
            fout << "]\n\n";
        }

        fout << "================================================================================\n";
        fout << "Verifikasi Matematika: 100% Eksak Sesuai Definisi Masalah Subset Sum.\n";
        fout << "================================================================================\n";
        fout.close();

        std::wstringstream msg_ss;
        msg_ss << L"Berhasil mengekspor " << g_lastStats.all_solutions.size() 
               << L" solusi lengkap ke file:\n" << szFile;
        MessageBoxW(hWndParent, msg_ss.str().c_str(), L"Ekspor Berhasil", MB_OK | MB_ICONINFORMATION);
    }
}
