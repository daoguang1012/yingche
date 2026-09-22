// Modified for Yingche: preserve UTF-8 Windows resource paths (2026-09-22).
#include "gpupixel/gpupixel.h"
#include "utils/util.h"

namespace gpupixel {

void GPUPixel::SetResourcePath(const std::string& path) {
  Util::SetResourcePath(fs::u8path(path));
}
}  // namespace gpupixel
