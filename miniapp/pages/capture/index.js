Page({
  data: {
    devicePosition: "front",
    photoPath: "",
    takingPhoto: false,
    permissionDenied: false
  },

  onReady() {
    this.cameraContext = wx.createCameraContext();
  },

  onShow() {
    this.inspectCameraPermission();
  },

  inspectCameraPermission() {
    wx.getSetting({
      success: (result) => {
        if (result.authSetting["scope.camera"] === false) {
          this.setData({ permissionDenied: true });
        }
      }
    });
  },

  handleCameraError() {
    this.setData({ permissionDenied: true });
  },

  openSettings() {
    wx.openSetting({
      success: (result) => {
        if (result.authSetting["scope.camera"]) {
          this.setData({ permissionDenied: false });
        }
      }
    });
  },

  switchCamera() {
    const next = this.data.devicePosition === "front" ? "back" : "front";
    this.setData({ devicePosition: next });
  },

  chooseFromAlbum() {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType: ["album"],
      success: (result) => {
        const filePath = result.tempFilePaths[0];
        if (filePath) {
          this.setData({ photoPath: filePath });
        }
      }
    });
  },

  takePhoto() {
    if (this.data.permissionDenied) {
      wx.showModal({
        title: "需要相机权限",
        content: "请先允许小程序使用相机，才能完成自拍上传。",
        showCancel: false
      });
      return;
    }
    if (!this.cameraContext || this.data.takingPhoto) {
      return;
    }

    this.setData({ takingPhoto: true });
    this.cameraContext.takePhoto({
      quality: "high",
      success: (result) => {
        this.setData({
          photoPath: result.tempImagePath || "",
          takingPhoto: false
        });
      },
      fail: () => {
        this.setData({ takingPhoto: false });
        wx.showToast({
          title: "拍照失败，请重试",
          icon: "none"
        });
      }
    });
  },

  retakePhoto() {
    this.setData({ photoPath: "" });
  },

  confirmPhoto() {
    if (!this.data.photoPath) {
      return;
    }

    const eventChannel = this.getOpenerEventChannel();
    eventChannel.emit("captured", { filePath: this.data.photoPath });
    wx.navigateBack();
  }
});
