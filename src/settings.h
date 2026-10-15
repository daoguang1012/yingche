#pragma once
#include <QJsonObject>
#include <QString>
#include <array>

struct Parameter {
    const char* key;
    const char* label;
    int minimum, maximum, initial;
};
inline constexpr std::array<Parameter, 12> parameters{{
    {"smooth", "磨皮", 0, 65, 25},
    {"detail", "纹理保留", 0, 100, 70},
    {"white", "肤色提亮", -30, 65, 10},
    {"warm", "冷暖肤色", -30, 30, 0},
    {"pink", "红润", 0, 40, 5},
    {"slim", "瘦脸 / 丰脸", -20, 30, 0},
    {"eyes", "大眼 / 小眼", -20, 30, 0},
    {"chin", "下巴长度", -20, 20, 0},
    {"nose", "鼻翼收窄", -20, 20, 0},
    {"lip", "唇色", 0, 40, 0},
    {"blush", "腮红", 0, 40, 0},
    {"sharp", "局部清晰度", 0, 45, 8}
}};
inline QJsonObject defaultBeauty() {
    QJsonObject o;
    for (const auto& p : parameters)
        o[QString::fromLatin1(p.key)] = p.initial;
    return o;
}
inline QJsonObject sanitizeBeauty(const QJsonObject& input) {
    QJsonObject o = defaultBeauty();
    for (const auto& p : parameters) {
        const auto key = QString::fromLatin1(p.key);
        if (input.value(key).isDouble())
            o[key] = qBound(p.minimum, input.value(key).toInt(p.initial), p.maximum);
    }
    return o;
}
