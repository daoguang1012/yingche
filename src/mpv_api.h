#pragma once
#include <QLibrary>
#include <QString>
#include <mpv/client.h>
#include <mpv/render_gl.h>

class MpvApi {
public:
    QLibrary library;
#define MPV_FUNCTION(name) decltype(&mpv_##name) name = nullptr
    MPV_FUNCTION(create);
    MPV_FUNCTION(initialize);
    MPV_FUNCTION(terminate_destroy);
    MPV_FUNCTION(set_option_string);
    MPV_FUNCTION(set_property_string);
    MPV_FUNCTION(get_property);
    MPV_FUNCTION(get_property_string);
    MPV_FUNCTION(command);
    MPV_FUNCTION(command_async);
    MPV_FUNCTION(wait_event);
    MPV_FUNCTION(observe_property);
    MPV_FUNCTION(set_wakeup_callback);
    MPV_FUNCTION(request_log_messages);
    MPV_FUNCTION(free);
    MPV_FUNCTION(error_string);
    MPV_FUNCTION(render_context_create);
    MPV_FUNCTION(render_context_set_update_callback);
    MPV_FUNCTION(render_context_update);
    MPV_FUNCTION(render_context_render);
    MPV_FUNCTION(render_context_report_swap);
    MPV_FUNCTION(render_context_free);
#undef MPV_FUNCTION
    bool load(const QString& path, QString& error) {
        library.setFileName(path);
        if (!library.load()) { error = library.errorString(); return false; }
#define LOAD(name) name = reinterpret_cast<decltype(name)>(library.resolve("mpv_" #name)); if (!name) { error = QStringLiteral("缺少 mpv 接口: " #name); return false; }
        LOAD(create); LOAD(initialize); LOAD(terminate_destroy);
        LOAD(set_option_string); LOAD(set_property_string);
        LOAD(get_property); LOAD(get_property_string);
        LOAD(command); LOAD(command_async); LOAD(wait_event);
        LOAD(observe_property); LOAD(set_wakeup_callback); LOAD(request_log_messages);
        LOAD(free); LOAD(error_string); LOAD(render_context_create);
        LOAD(render_context_set_update_callback); LOAD(render_context_update);
        LOAD(render_context_render); LOAD(render_context_report_swap); LOAD(render_context_free);
#undef LOAD
        return true;
    }
};
