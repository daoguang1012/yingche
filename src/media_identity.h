#pragma once
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QString>
#include <QDateTime>

// Bounded content identity: at most 192 KiB, independent of name/path/mtime.
// This is not a full-file integrity hash. Unreadable files must never share a key.
inline QString mediaIdentity(const QString& path) {
    QFile file(path);
    if(!file.open(QIODevice::ReadOnly) || file.size()<=0) return {};
    const qint64 size=file.size(),chunk=65536;
    const auto modified=QFileInfo(file).lastModified();
    QCryptographicHash hash(QCryptographicHash::Sha256);
    hash.addData(QByteArray("yingche-media-v1:")+QByteArray::number(size));
    for(qint64 offset:{qint64(0),qMax(qint64(0),(size-chunk)/2),qMax(qint64(0),size-chunk)}) {
        if(!file.seek(offset))return {};
        const auto bytes=file.read(qMin(chunk,size-offset));
        if(bytes.size()!=qMin(chunk,size-offset))return {};
        hash.addData(QByteArray::number(offset)+':'); hash.addData(bytes);
    }
    if(file.size()!=size || QFileInfo(file).lastModified()!=modified)return {};
    return QString::fromLatin1(hash.result().toHex());
}
