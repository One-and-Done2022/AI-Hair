const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request, uploadFile } = require("../../utils/request");

const BLOCK_LABELS = {
  shot: "构图景别",
  scene_environment: "场景环境",
  scene_lighting: "场景光线",
  scene_mood: "场景氛围",
  expression: "人物表情",
  subject_action: "主体动作",
  outfit: "人物服饰",
  scene_constraints: "场景约束"
};

function splitInputList(value) {
  return (value || "")
    .replace(/\n/g, "；")
    .split(/[；;,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildBlockItems(blocks = {}) {
  return Object.keys(BLOCK_LABELS)
    .filter((key) => !!blocks[key])
    .map((key) => ({
      key,
      label: BLOCK_LABELS[key],
      value: blocks[key]
    }));
}

Page({
  data: {
    selectedImage: "",
    analyzing: false,
    titleInput: "",
    selectedStyleLine: "",
    detailTagsInput: "",
    pairingAdviceInput: "",
    referenceNotesInput: "",
    uploadId: "",
    modelName: "",
    blockItems: [],
    sceneDraftJson: "",
    fullResponseJson: ""
  },

  async onLoad() {
    try {
      await ensureLogin();
    } catch (error) {
      showError(error, { fallback: "登录失败，请稍后再试" });
    }
  },

  chooseImage() {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType: ["album"],
      success: (result) => {
        const filePath = result.tempFilePaths[0];
        if (!filePath) {
          return;
        }
        this.setData({
          selectedImage: filePath,
          uploadId: "",
          modelName: "",
          blockItems: [],
          sceneDraftJson: "",
          fullResponseJson: ""
        });
      }
    });
  },

  previewImage() {
    if (!this.data.selectedImage) {
      return;
    }
    wx.previewImage({
      urls: [this.data.selectedImage]
    });
  },

  clearImage() {
    this.setData({
      selectedImage: "",
      uploadId: "",
      modelName: "",
      blockItems: [],
      sceneDraftJson: "",
      fullResponseJson: ""
    });
  },

  handleTitleInput(event) {
    this.setData({ titleInput: event.detail.value || "" });
  },

  handleDetailTagsInput(event) {
    this.setData({ detailTagsInput: event.detail.value || "" });
  },

  handlePairingAdviceInput(event) {
    this.setData({ pairingAdviceInput: event.detail.value || "" });
  },

  handleReferenceNotesInput(event) {
    this.setData({ referenceNotesInput: event.detail.value || "" });
  },

  selectStyleLine(event) {
    const { value } = event.currentTarget.dataset;
    if (!value) {
      return;
    }
    this.setData({
      selectedStyleLine: this.data.selectedStyleLine === value ? "" : value
    });
  },

  async analyzeScene() {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传参考图",
        icon: "none"
      });
      return;
    }

    this.setData({ analyzing: true });
    wx.showLoading({ title: "正在生成草案" });

    try {
      await ensureLogin();
      const upload = await uploadFile({
        url: "/api/uploads",
        filePath: this.data.selectedImage,
        name: "file",
        timeout: 20000
      });

      const payload = {
        upload_id: upload.upload_id
      };

      const title = this.data.titleInput.trim();
      const styleLine = this.data.selectedStyleLine;
      const detailTags = splitInputList(this.data.detailTagsInput);
      const pairingAdvice = splitInputList(this.data.pairingAdviceInput);
      const referenceNotes = this.data.referenceNotesInput.trim();

      if (title) {
        payload.title = title;
      }
      if (styleLine) {
        payload.style_line = styleLine;
      }
      if (detailTags.length) {
        payload.detail_tags = detailTags;
      }
      if (pairingAdvice.length) {
        payload.pairing_advice = pairingAdvice;
      }
      if (referenceNotes) {
        payload.reference_notes = referenceNotes;
      }

      const response = await request({
        url: "/api/scene-understanding",
        method: "POST",
        data: payload,
        timeout: 90000
      });

      this.setData({
        uploadId: response.upload_id || "",
        modelName: response.model_name || "",
        blockItems: buildBlockItems(response.blocks),
        sceneDraftJson: JSON.stringify(response.scene_draft, null, 2),
        fullResponseJson: JSON.stringify(response, null, 2)
      });

      wx.showToast({
        title: "草案已生成",
        icon: "success"
      });
    } catch (error) {
      showError(error, { fallback: "生成场景草案失败，请稍后再试" });
    } finally {
      wx.hideLoading();
      this.setData({ analyzing: false });
    }
  },

  copySceneDraft() {
    if (!this.data.sceneDraftJson) {
      return;
    }
    wx.setClipboardData({
      data: this.data.sceneDraftJson
    });
  },

  copyFullResponse() {
    if (!this.data.fullResponseJson) {
      return;
    }
    wx.setClipboardData({
      data: this.data.fullResponseJson
    });
  }
});
