function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function toOptionItems(items) {
  return (items || []).map((item) => ({ id: item, label: item }));
}

function findBackendById(items, id) {
  return findById(items || [], id);
}

function formatGenerationBackends(backends = []) {
  return backends.map((item) => {
    if (item.id === "basic") {
      return {
        ...item,
        description: "用基础模型，返回 1 张换发预览和 2 张场景成片"
      };
    }
    if (item.id === "premium") {
      return {
        ...item,
        description: "用高级模型，返回 1 张换发预览和 2 张场景成片"
      };
    }
    return item;
  });
}

function buildGenerationSelection(backends, cachedOptions = {}) {
  const availableBackends = (backends || []).filter((item) => item.enabled);
  const fallbackBackends = availableBackends.length ? availableBackends : backends || [];
  const selectedBackend =
    findBackendById(fallbackBackends, cachedOptions.generator_backend) ||
    fallbackBackends[0] ||
    null;
  const aspectRatios = selectedBackend ? selectedBackend.aspect_ratios || [] : [];
  const resolutions = selectedBackend ? selectedBackend.resolutions || [] : [];
  const selectedAspectRatio =
    (aspectRatios.includes(cachedOptions.aspect_ratio) && cachedOptions.aspect_ratio) ||
    (selectedBackend && selectedBackend.default_aspect_ratio) ||
    aspectRatios[0] ||
    "3:4";
  const selectedResolution = resolutions.length
    ? (
        (resolutions.includes(cachedOptions.resolution) && cachedOptions.resolution) ||
        (selectedBackend && selectedBackend.default_resolution) ||
        resolutions[0]
      )
    : "";

  return {
    selectedBackend,
    selectedGeneratorBackend: selectedBackend ? selectedBackend.id : "",
    selectedAspectRatio,
    selectedResolution,
    aspectRatioOptions: toOptionItems(aspectRatios),
    resolutionOptions: toOptionItems(resolutions)
  };
}

module.exports = {
  buildGenerationSelection,
  findBackendById,
  findById,
  formatGenerationBackends
};
