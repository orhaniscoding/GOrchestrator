# GOrchestrator Complete System Diagram

This diagram shows the complete GOrchestrator system including all components, interactions, and flows.

## How to View

1. Copy the Mermaid code below
2. Go to [Mermaid Live Editor](https://mermaid.live/)
3. Paste the code and view the diagram

## Mermaid Code

```mermaid
flowchart TD
    %% ================================================================
    %% GOrchestrator Complete System Diagram
    %% ================================================================
    
    %% ================================================================
    %% Entry Points
    %% ================================================================
    subgraph Entry["Entry Points"]
        CLI["CLI (gorchestrator.py)"]
        API["API (Future)"]
    end
    
    %% ================================================================
    %% Configuration Layer
    %% ================================================================
    subgraph Config["Configuration Layer"]
        ENV["".env File""]
        YAMLS["Manager Profiles YAML"]
        SETTINGS["Settings (config.py)"]
        GET_SETTINGS["get_settings()"]
        RELOAD_SETTINGS["reload_settings()"]
        WRITE_ENV["write_env_value()"]
        VALIDATE_CONFIG["validate_config()"]
    end
    
    %% ================================================================
    %% UI Layer
    %% ================================================================
    subgraph UI["UI Layer"]
        CONSOLE_UI["ConsoleUI (ui/console.py)"]
        PROMPT["get_user_input()"]
        PRINT_HEADER["print_header()"]
        PRINT_SUCCESS["print_success()"]
        PRINT_ERROR["print_error()"]
        PRINT_INFO["print_info()"]
        PRINT_WARNING["print_warning()"]
        PRINT_SETTINGS["print_settings()"]
        PRINT_DASHBOARD["print_dashboard()"]
        SHOW_HISTORY["show_history()"]
        VERBOSE["verbose_worker flag"]
        CLEAR["clear()"]
    end
    
    %% ================================================================
    %% Command System
    %% ================================================================
    subgraph CommandSys["Command System"]
        PARSER["CommandParser (commands/parser.py)"]
        COMMAND["Command Dataclass"]
        PARSE["parse()"]
        VALIDATE["validate()"]
        GET_SUGGESTIONS["get_suggestions()"]
        COMMAND_TREE["COMMAND_TREE"]
        
        HANDLER["CommandHandler (commands/handlers.py)"]
        HANDLE["handle()"]
        HANDLE_MANAGER["_handle_manager()"]
        HANDLE_WORKER["_handle_worker()"]
        HANDLE_SESSION["_handle_session()"]
        HANDLE_SYSTEM["_handle_system()"]
        HANDLE_MODE["_handle_mode()"]
        
        COMPLETER["TabCompleter (commands/completer.py)"]
        GET_COMPLETIONS["get_completions()"]
        BUILD_TREE["build_completer_tree()"]
        COMPLETER_TREE["Completer Tree"]
        DYNAMIC_COMPLETIONS["get_dynamic_completions()"]
        
        HELP_SYSTEM["HelpSystem (commands/help.py)"]
        SHOW_MAIN["show_main_help()"]
        SHOW_CMD["show_command_help()"]
        GET_CMD_DOC["get_command_doc()"]
        GET_MANAGER_DOC["_get_manager_doc()"]
        GET_WORKER_DOC["_get_worker_doc()"]
        GET_SESSION_DOC["_get_session_doc()"]
        GET_SYSTEM_DOC["_get_system_doc()"]
        GET_MODE_DOC["_get_mode_doc()"]
    end
    
    %% ================================================================
    %% Core Engine Layer
    %% ================================================================
    subgraph Core["Core Engine Layer"]
        ENGINE["SessionEngine (engine.py)"]
        START_INTERACTIVE["start_interactive_mode()"]
        HANDLE_SLASH["_handle_slash_command()"]
        AUTO_SAVE["_auto_save()"]
        NEW_SESSION["_new_session()"]
        SAVE_SESSION["save_session()"]
        LOAD_SESSION["load_session()"]
        LIST_SESSIONS["list_sessions()"]
        GET_LAST_SESSION["_get_last_session_id()"]
        
        INIT_MANAGER["_init_manager()"]
        REFRESH_TOOLS["_refresh_manager_tools()"]
        APPLY_WORKER["_apply_active_worker()"]
        VALIDATE_STARTUP["_validate_config_on_startup()"]
        
        PROCESS_MSG["_process_user_message()"]
        CHECK_CONFIRM["_check_confirm_mode()"]
        
        CHECKPOINT_STACK["_checkpoint_stack"]
        LOAD_CHECKPOINTS["_load_checkpoints_from_git()"]
        LIST_CHECKPOINTS["_list_checkpoints()"]
        RESTORE_CHECKPOINT["_restore_checkpoint()"]
        IS_GIT_REPO["_is_git_repo()"]
    end
    
    %% ================================================================
    %% Agent Layer
    %% ================================================================
    subgraph Agents["Agent Layer"]
        MANAGER["ManagerAgent (manager.py)"]
        MANAGER_INIT["__init__()"]
        MANAGER_SETTINGS["settings"]
        MANAGER_WORKER["worker"]
        MANAGER_HISTORY["history"]
        MANAGER_MESSAGES["messages"]
        
        MANAGER_CHAT["chat()"]
        MANAGER_STREAM["stream()"]
        MANAGER_CALL["__call__()"]
        MANAGER_GET_HISTORY["get_history()"]
        MANAGER_CLEAR_HISTORY["clear_history()"]
        MANAGER_REFRESH["refresh_system_prompt()"]
        MANAGER_REFRESH_TOOLS["refresh_tools()"]
        
        WORKER["AgentWorker (worker.py)"]
        WORKER_INIT["__init__()"]
        WORKER_SETTINGS["settings"]
        WORKER_LLM["llm_client"]
        WORKER_STATE["state"]
        
        WORKER_RUN["run()"]
        WORKER_STREAM["stream()"]
        WORKER_CALL["__call__()"]
        WORKER_EXECUTE["execute_tool()"]
        WORKER_GET_STATE["get_state()"]
    end
    
    %% ================================================================
    %% Worker Registry Layer
    %% ================================================================
    subgraph Registry["Worker Registry Layer"]
        WORKER_REGISTRY["WorkerRegistry (worker_registry.py)"]
        WR_INIT["__init__()"]
        WR_FILE["registry_file"]
        WR_WORKERS["workers"]
        
        WR_ADD["add()"]
        WR_REMOVE["remove()"]
        WR_GET["get()"]
        WR_GET_PRIMARY["get_primary()"]
        WR_GET_ACTIVE["get_active_workers()"]
        WR_LIST["list_all()"]
        WR_SET_ACTIVE["set_active()"]
        WR_SET_INACTIVE["set_inactive()"]
        WR_SET_PRIMARY["set_primary()"]
        WR_UPDATE_MODEL["update_model()"]
        WR_UPDATE_PROFILE["update_profile()"]
        WR_UPDATE_API["update_api()"]
        WR_ENSURE_DEFAULT["ensure_default()"]
        WR_SYNC["sync_to_settings()"]
        WR_SANITIZE["sanitize_name()"]
        WR_SAVE["save()"]
        WR_LOAD["load()"]
    end
    
    %% ================================================================
    %% Session Storage Layer
    %% ================================================================
    subgraph Storage["Session Storage Layer"]
        SESSIONS_DIR["SESSIONS_DIR"]
        SESSION_DIR["_session_dir"]
        SESSION_FILE["session.json"]
        MESSAGES_FILE["messages.json"]
        
        LIST_SESSIONS["list_sessions()"]
        GET_SESSION_ID["get_session_id()"]
        GET_SESSION_NAME["get_session_name()"]
    end
    
    %% ================================================================
    %% LLM Layer (LiteLLM-based, no separate LLM client module)
    %% ================================================================
    subgraph LLM["LLM Integration Layer"]
        LITELLM["LiteLLM (litellm library)"]
        DETECT_PROVIDER["detect_provider()"]
        STRIP_PREFIX["strip_provider_prefix()"]
        CALL_LITELLM["call_litellm()"]
        MASK_KEYS["mask_api_keys()"]
    end

    %% ================================================================
    %% Sub-Manager & LLM Pool Layer
    %% ================================================================
    subgraph MoA["Mixture of Agents Layer"]
        SUB_MANAGER["SubManagerAgent (sub_manager.py)"]
        SM_REGISTRY["SubManagerRegistry"]
        SM_CONFIG["SubManagerConfig"]
        SM_RESPONSE["SubManagerResponse"]

        LLM_POOL["LLMPool (llm_pool.py)"]
        LLM_CONFIG["LLMConfig"]
        LLM_RESPONSE["LLMResponse"]
    end

    %% ================================================================
    %% Team & Checkpoint Layer
    %% ================================================================
    subgraph TeamLayer["Team & Safety Layer"]
        TEAM_REGISTRY["TeamRegistry (team.py)"]
        TEAM_CONFIG["TeamConfig"]

        CHECKPOINT_MGR["CheckpointManager (checkpoint_manager.py)"]
        CP_CREATE["create()"]
        CP_RESTORE["restore()"]
        CP_LIST["list_checkpoints()"]
    end

    %% ================================================================
    %% Base Registry
    %% ================================================================
    subgraph BaseRegistry["Registry Infrastructure"]
        JSON_REGISTRY["JsonRegistry (json_registry.py)"]
        JR_LOAD["_load() - JSONDecodeError handling"]
        JR_SAVE["_save() - atomic temp+os.replace"]
        JR_SANITIZE["sanitize_name()"]
    end
    
    %% ================================================================
    %% Session Mode
    %% ================================================================
    subgraph Mode["Session Mode"]
        SESSION_MODE["SessionMode Enum"]
        MODE_AUTO["AUTO"]
        MODE_VERBOSE["VERBOSE"]
    end
    
    %% ================================================================
    %% Main Flow
    %% ================================================================
    
    %% Program Start
    CLI -->|"main.py"| START_INTERACTIVE
    API -->|"Future"| ENGINE
    
    %% Settings Load
    START_INTERACTIVE -->|"1. Load Settings"| GET_SETTINGS
    GET_SETTINGS -->|"read"| ENV
    ENV -->|"parse"| SETTINGS
    SETTINGS -->|"validate"| VALIDATE_CONFIG
    
    %% Session Engine Init
    VALIDATE_CONFIG -->|"2. Create Engine"| ENGINE
    ENGINE -->|"create"| CONSOLE_UI
    CONSOLE_UI -->|"set verbose"| VERBOSE
    ENGINE -->|"create"| PARSER
    ENGINE -->|"create"| HANDLER
    ENGINE -->|"create"| COMPLETER
    ENGINE -->|"create"| HELP_SYSTEM
    ENGINE -->|"create"| WORKER_REGISTRY
    
    %% Worker Registry Init
    WORKER_REGISTRY -->|"load"| WR_FILE
    WR_LOAD -->|"read"| WR_WORKERS
    WORKER_REGISTRY -->|"ensure default"| WR_ENSURE_DEFAULT
    WR_ENSURE_DEFAULT -->|"create"| WR_ADD
    
    %% Manager Init
    ENGINE -->|"3. Init Manager"| INIT_MANAGER
    INIT_MANAGER -->|"create"| MANAGER
    MANAGER -->|"set"| MANAGER_SETTINGS
    MANAGER -->|"create"| WORKER
    WORKER -->|"set"| WORKER_SETTINGS
    WORKER_SETTINGS -->|"create"| LLM_CLIENT
    
    %% Checkpoint Load
    ENGINE -->|"4. Load Checkpoints"| LOAD_CHECKPOINTS
    LOAD_CHECKPOINTS -->|"git tag"| CHECKPOINT_STACK
    LOAD_CHECKPOINTS -->|"check"| IS_GIT_REPO
    
    %% Session Load
    ENGINE -->|"5. Get Last Session"| GET_LAST_SESSION
    GET_LAST_SESSION -->|"check"| STORAGE
    STORAGE -->|"read"| SESSIONS_DIR
    STORAGE -->|"find"| SESSION_DIR
    
    %% Interactive Loop Start
    START_INTERACTIVE -->|"6. Start Loop"| ENGINE
    ENGINE -->|"print header"| PRINT_HEADER
    ENGINE -->|"print dashboard"| PRINT_DASHBOARD
    ENGINE -->|"print info"| PRINT_INFO
    
    %% User Input Loop
    subgraph Loop["Interactive Loop"]
        ENGINE -->|"7. Get Input"| PROMPT
        PROMPT -->|"user input"| USER_INPUT["user_input: str"]
        
        USER_INPUT -->|"starts with /"?| COMMAND_CHECK{Is Slash Command?}
        
        %% Slash Command Path
        COMMAND_CHECK -->|"Yes"| HANDLE_SLASH
        HANDLE_SLASH -->|"check source"| NEW_CMD_CHECK{New Command?}
        
        NEW_CMD_CHECK -->|"/manager, /worker, /session,<br>/system, /mode, /help"| PARSE
        PARSE -->|"parse"| PARSER
        PARSER -->|"return"| COMMAND
        COMMAND -->|"validate"| VALIDATE
        VALIDATE -->|"valid"?| VALID_CMD{Valid?}
        
        VALID_CMD -->|"Yes"| HANDLE
        HANDLE -->|"dispatch"| HANDLE_SOURCE{Source?}
        
        HANDLE_SOURCE -->|"manager"| HANDLE_MANAGER
        HANDLE_SOURCE -->|"worker"| HANDLE_WORKER
        HANDLE_SOURCE -->|"session"| HANDLE_SESSION
        HANDLE_SOURCE -->|"system"| HANDLE_SYSTEM
        HANDLE_SOURCE -->|"mode"| HANDLE_MODE
        HANDLE_SOURCE -->|"help"| SHOW_CMD
        
        VALID_CMD -->|"No"| OLD_CMD_CHECK{Old Command?}
        OLD_CMD_CHECK -->|"/save, /load, /list,<br>/new, /verbose, /quiet,<br>/confirm, /clear"| OLD_HANDLER["Existing Handlers"]
        OLD_CMD_CHECK -->|"No"| PRINT_ERROR
        
        %% Manager Handlers
        HANDLE_MANAGER -->|"show"| MANAGER_SHOW["_manager_show_config()"]
        HANDLE_MANAGER -->|"set profile"| SET_PROFILE["_manager_set_profile()"]
        HANDLE_MANAGER -->|"set model"| SET_MODEL["_manager_set_model()"]
        HANDLE_MANAGER -->|"set api"| SET_API["_manager_set_api()"]
        HANDLE_MANAGER -->|"set prompt"| SET_PROMPT["_manager_set_prompt()"]
        
        SET_MODEL -->|"--global"?| MODEL_CHECK{Global?}
        MODEL_CHECK -->|"Yes"| WRITE_ENV
        MODEL_CHECK -->|"No"| SETTINGS_OVERRIDE["MANAGER_MODEL_OVERRIDE"]
        
        SET_API -->|"--global"?| API_CHECK{Global?}
        API_CHECK -->|"Yes"| WRITE_ENV
        API_CHECK -->|"No"| SETTINGS_OVERRIDE
        
        WRITE_ENV -->|"write"| ENV
        
        %% Worker Handlers
        HANDLE_WORKER -->|"list"| WORKER_LIST["_worker_list()"]
        HANDLE_WORKER -->|"show"| WORKER_SHOW["_worker_show()"]
        HANDLE_WORKER -->|"add"| WORKER_ADD["_worker_add()"]
        HANDLE_WORKER -->|"remove"| WORKER_REMOVE["_worker_remove()"]
        HANDLE_WORKER -->|"set"| WORKER_SET["_worker_set()"]
        
        WORKER_ADD -->|"call"| WR_ADD
        WR_ADD -->|"add to registry"| WR_WORKERS
        WR_ADD -->|"save to file"| WR_SAVE
        
        WORKER_REMOVE -->|"call"| WR_REMOVE
        WR_REMOVE -->|"remove from registry"| WR_WORKERS
        WR_REMOVE -->|"save to file"| WR_SAVE
        
        WORKER_SET -->|"active"| WR_SET_ACTIVE
        WORKER_SET -->|"inactive"| WR_SET_INACTIVE
        WORKER_SET -->|"primary"| WR_SET_PRIMARY
        WORKER_SET -->|"model"| WR_UPDATE_MODEL
        WORKER_SET -->|"profile"| WR_UPDATE_PROFILE
        WORKER_SET -->|"api"| WR_UPDATE_API
        
        %% Session Handlers
        HANDLE_SESSION -->|"list"| SESSION_LIST["_session_list()"]
        HANDLE_SESSION -->|"show"| SESSION_SHOW["_session_show()"]
        HANDLE_SESSION -->|"save"| SESSION_SAVE["_session_save()"]
        HANDLE_SESSION -->|"new"| SESSION_NEW["_session_new()"]
        HANDLE_SESSION -->|"load"| SESSION_LOAD["_session_load()"]
        HANDLE_SESSION -->|"export"| SESSION_EXPORT["_session_export()"]
        
        SESSION_LIST -->|"call"| LIST_SESSIONS
        LIST_SESSIONS -->|"read"| SESSIONS_DIR
        
        SESSION_SAVE -->|"call"| SAVE_SESSION
        SAVE_SESSION -->|"write"| SESSION_FILE
        
        SESSION_NEW -->|"call"| NEW_SESSION
        NEW_SESSION -->|"create"| SESSION_DIR
        NEW_SESSION -->|"clear"| MANAGER_CLEAR_HISTORY["clear_history()"]
        
        SESSION_LOAD -->|"call"| LOAD_SESSION
        LOAD_SESSION -->|"read"| SESSION_FILE
        LOAD_SESSION -->|"load messages"| MESSAGES_FILE
        
        %% System Handlers
        HANDLE_SYSTEM -->|"show"| SYSTEM_SHOW["_system_show()"]
        HANDLE_SYSTEM -->|"validate"| SYSTEM_VALIDATE["_system_validate()"]
        HANDLE_SYSTEM -->|"reload"| SYSTEM_RELOAD["_system_reload()"]
        HANDLE_SYSTEM -->|"reset"| SYSTEM_RESET["_system_reset()"]
        
        SYSTEM_VALIDATE -->|"call"| VALIDATE_CONFIG
        
        SYSTEM_RELOAD -->|"call"| RELOAD_SETTINGS
        RELOAD_SETTINGS -->|"reload"| ENV
        RELOAD_SETTINGS -->|"new settings"| SETTINGS
        RELOAD_SETTINGS -->|"update"| MANAGER_SETTINGS
        RELOAD_SETTINGS -->|"update"| WORKER_SETTINGS
        RELOAD_SETTINGS -->|"update"| CONSOLE_UI
        RELOAD_SETTINGS -->|"sync"| WR_SYNC
        
        %% Mode Handlers
        HANDLE_MODE -->|"verbose"| MODE_VERBOSE["_mode_verbose()"]
        HANDLE_MODE -->|"quiet"| MODE_QUIET["_mode_quiet()"]
        HANDLE_MODE -->|"confirm on"| MODE_CONFIRM_ON["_mode_confirm(True)"]
        HANDLE_MODE -->|"confirm off"| MODE_CONFIRM_OFF["_mode_confirm(False)"]
        
        MODE_VERBOSE -->|"set"| VERBOSE
        VERBOSE -->|"True"| MODE_VERBOSE
        MODE_QUIET -->|"set"| VERBOSE
        VERBOSE -->|"False"| MODE_QUIET
        
        %% Help Handlers
        SHOW_CMD -->|"no arg"| SHOW_MAIN
        SHOW_CMD -->|"with arg"| SHOW_CMD
        
        SHOW_MAIN -->|"print"| CONSOLE_UI
        SHOW_CMD -->|"print"| CONSOLE_UI
        
        %% Non-Command Path (Manager Chat)
        COMMAND_CHECK -->|"No"| PROCESS_MSG
        PROCESS_MSG -->|"check"| CHECK_CONFIRM
        CHECK_CONFIRM -->|"confirm"?| CONFIRM_CHECK{Confirm Mode?}
        CONFIRM_CHECK -->|"Yes"| PROMPT
        CONFIRM_CHECK -->|"No"| MANAGER_CHAT
        
        PROMPT -->|"confirmed"| MANAGER_CHAT
        PROMPT -->|"cancelled"| PRINT_INFO
        
        MANAGER_CHAT -->|"call"| MANAGER_CALL
        MANAGER_CALL -->|"get config"| MANAGER_GET_CONFIG
        MANAGER_GET_CONFIG -->|"get manager config"| SETTINGS
        
        MANAGER_CALL -->|"create task"| MANAGER_TASK["Manager creates task"]
        MANAGER_TASK -->|"delegate to worker"| WORKER_RUN
        
        %% Worker Execution
        WORKER_RUN -->|"get state"| WORKER_GET_STATE
        WORKER_GET_STATE -->|"read"| WORKER_STATE
        
        WORKER_RUN -->|"get config"| LLM_GET_CONFIG
        LLM_GET_CONFIG -->|"get worker config"| SETTINGS
        
        WORKER_RUN -->|"call LLM"| LLM_CALL
        LLM_CALL -->|"stream"| LLM_STREAM
        LLM_STREAM -->|"print output"| CONSOLE_UI
        
        WORKER_RUN -->|"execute tool"| WORKER_EXECUTE
        WORKER_EXECUTE -->|"tool result"| WORKER_TASK["Worker completes task"]
        WORKER_TASK -->|"return to manager"| MANAGER
        
        MANAGER -->|"update history"| MANAGER_HISTORY
        MANAGER_HISTORY -->|"append"| MANAGER_MESSAGES
        
        %% Loop Continue
        MANAGER_SHOW -->|"return True"| LOOP_CONTINUE{"Continue?"}
        SET_PROFILE -->|"return True"| LOOP_CONTINUE
        SET_MODEL -->|"return True"| LOOP_CONTINUE
        SET_API -->|"return True"| LOOP_CONTINUE
        SET_PROMPT -->|"return True"| LOOP_CONTINUE
        
        WORKER_LIST -->|"return True"| LOOP_CONTINUE
        WORKER_SHOW -->|"return True"| LOOP_CONTINUE
        WORKER_ADD -->|"return True"| LOOP_CONTINUE
        WORKER_REMOVE -->|"return True"| LOOP_CONTINUE
        WORKER_SET -->|"return True"| LOOP_CONTINUE
        
        SESSION_LIST -->|"return True"| LOOP_CONTINUE
        SESSION_SHOW -->|"return True"| LOOP_CONTINUE
        SESSION_SAVE -->|"return True"| LOOP_CONTINUE
        SESSION_NEW -->|"return True"| LOOP_CONTINUE
        SESSION_LOAD -->|"return True"| LOOP_CONTINUE
        SESSION_EXPORT -->|"return True"| LOOP_CONTINUE
        
        SYSTEM_SHOW -->|"return True"| LOOP_CONTINUE
        SYSTEM_VALIDATE -->|"return True"| LOOP_CONTINUE
        SYSTEM_RELOAD -->|"return True"| LOOP_CONTINUE
        SYSTEM_RESET -->|"return True"| LOOP_CONTINUE
        
        MODE_VERBOSE -->|"return True"| LOOP_CONTINUE
        MODE_QUIET -->|"return True"| LOOP_CONTINUE
        MODE_CONFIRM_ON -->|"return True"| LOOP_CONTINUE
        MODE_CONFIRM_OFF -->|"return True"| LOOP_CONTINUE
        
        SHOW_MAIN -->|"return True"| LOOP_CONTINUE
        SHOW_CMD -->|"return True"| LOOP_CONTINUE
        
        OLD_HANDLER -->|"return True"| LOOP_CONTINUE
        PRINT_ERROR -->|"return False"| LOOP_CONTINUE
        
        MANAGER_TASK -->|"return result"| LOOP_CONTINUE
        WORKER_TASK -->|"return result"| LOOP_CONTINUE
        
        MANAGER_CHAT -->|"return result"| LOOP_CONTINUE
        
        LOOP_CONTINUE -->|"Yes"| PROMPT
        LOOP_CONTINUE -->|"No"| EXIT
    end
    
    %% ================================================================
    %% Tab Completion Flow
    %% ================================================================
    subgraph CompletionFlow["Tab Completion Flow"]
        USER_INPUT -->|"TAB key"| GET_COMPLETIONS
        GET_COMPLETIONS -->|"state 0"| GET_SUGGESTIONS
        GET_SUGGESTIONS -->|"return"| ROOT_SUGGESTIONS["/manager, /worker, ..."]
        
        GET_COMPLETIONS -->|"state > 0"| BUILD_TREE
        BUILD_TREE -->|"build"| COMPLETER_TREE
        COMPLETER_TREE -->|"nested"| COMPLETER_TREE
        COMPLETER_TREE -->|"return"| NESTED_SUGGESTIONS["/manager show, /worker list, ..."]
        
        GET_COMPLETIONS -->|"context"| DYNAMIC_COMPLETIONS
        DYNAMIC_COMPLETIONS -->|"workers"| WORKER_NAMES["default, coder, ..."]
        DYNAMIC_COMPLETIONS -->|"sessions"| SESSION_IDS["20260211_143022, ..."]
    end
    
    %% ================================================================
    %% Styles
    %% ================================================================
    classDef entry fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef config fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef ui fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef command fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef core fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef agent fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef registry fill:#e0f2f1,stroke:#004d40,stroke-width:2px
    classDef storage fill:#efebe9,stroke:#3e2723,stroke-width:2px
    classDef llm fill:#e3f2fd,stroke:#0d47a1,stroke-width:2px
    classDef mode fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    
    class CLI,API entry
    class ENV,YAMLS,SETTINGS,GET_SETTINGS,RELOAD_SETTINGS,WRITE_ENV,VALIDATE_CONFIG config
    class CONSOLE_UI,PROMPT,PRINT_HEADER,PRINT_SUCCESS,PRINT_ERROR,PRINT_INFO,PRINT_WARNING,PRINT_SETTINGS,PRINT_DASHBOARD,SHOW_HISTORY,VERBOSE,CLEAR ui
    class PARSER,COMMAND,PARSE,VALIDATE,GET_SUGGESTIONS,COMMAND_TREE,HANDLER,HANDLE,HANDLE_MANAGER,HANDLE_WORKER,HANDLE_SESSION,HANDLE_SYSTEM,HANDLE_MODE,COMPLETER,GET_COMPLETIONS,BUILD_TREE,COMPLETER_TREE,DYNAMIC_COMPLETIONS,HELP_SYSTEM,SHOW_MAIN,SHOW_CMD,GET_CMD_DOC,GET_MANAGER_DOC,GET_WORKER_DOC,GET_SESSION_DOC,GET_SYSTEM_DOC,GET_MODE_DOC command
    class ENGINE,START_INTERACTIVE,HANDLE_SLASH,AUTO_SAVE,NEW_SESSION,SAVE_SESSION,LOAD_SESSION,LIST_SESSIONS,GET_LAST_SESSION,INIT_MANAGER,REFRESH_TOOLS,APPLY_WORKER,VALIDATE_STARTUP,PROCESS_MSG,CHECK_CONFIRM,CHECKPOINT_STACK,LOAD_CHECKPOINTS,LIST_CHECKPOINTS,RESTORE_CHECKPOINT,IS_GIT_REPO core
    class MANAGER,MANAGER_INIT,MANAGER_SETTINGS,MANAGER_WORKER,MANAGER_HISTORY,MANAGER_MESSAGES,MANAGER_CHAT,MANAGER_STREAM,MANAGER_CALL,MANAGER_GET_HISTORY,MANAGER_CLEAR_HISTORY,MANAGER_REFRESH,MANAGER_REFRESH_TOOLS,WORKER,WORKER_INIT,WORKER_SETTINGS,WORKER_LLM,WORKER_STATE,WORKER_RUN,WORKER_STREAM,WORKER_CALL,WORKER_EXECUTE,WORKER_GET_STATE agent
    class WORKER_REGISTRY,WR_INIT,WR_FILE,WR_WORKERS,WR_ADD,WR_REMOVE,WR_GET,WR_GET_PRIMARY,WR_GET_ACTIVE,WR_LIST,WR_SET_ACTIVE,WR_SET_INACTIVE,WR_SET_PRIMARY,WR_UPDATE_MODEL,WR_UPDATE_PROFILE,WR_UPDATE_API,WR_ENSURE_DEFAULT,WR_SYNC,WR_SANITIZE,WR_SAVE,WR_LOAD registry
    class SESSIONS_DIR,SESSION_DIR,SESSION_FILE,MESSAGES_FILE,LIST_SESSIONS,GET_SESSION_ID,GET_SESSION_NAME storage
    class LLM_CLIENT,LLM_INIT,LLM_SETTINGS,LLM_MODEL,LLM_API_BASE,LLM_API_KEY,LLM_CALL,LLM_STREAM,LLM_CHAT,LLM_GET_CONFIG llm
    class SESSION_MODE,MODE_AUTO,MODE_VERBOSE mode
```

## Diagram Summary

This diagram shows the complete GOrchestrator system architecture including:

1. **Entry Points** - CLI and API entry points
2. **Configuration Layer** - Settings, .env, YAML profiles
3. **UI Layer** - ConsoleUI, input/output handling
4. **Command System** - Parser, Handler, Completer, Help
5. **Core Engine** - SessionEngine and orchestration logic
6. **Agent Layer** - ManagerAgent and AgentWorker
7. **Worker Registry** - Worker management and storage
8. **Session Storage** - Session persistence
9. **LLM Client** - LLM integration
10. **Session Mode** - AUTO and VERBOSE modes

The diagram shows the complete flow from program start to interactive loop, including all command processing paths, agent execution flows, and tab completion logic.
