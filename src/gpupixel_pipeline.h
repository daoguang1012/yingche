#pragma once
#include <QJsonObject>
#include <QString>
#include <memory>
class GPUPixelPipeline final {
public:
 GPUPixelPipeline();~GPUPixelPipeline();
 bool initialize(const QString& root,QString& error);
 unsigned int render(unsigned int sourceFbo,int width,int height,const QJsonObject& params);
 void release();
private:
 struct Impl;std::unique_ptr<Impl> impl_;
};
