!pip install rasterio tensorflow scikit-learn matplotlib -q

from google.colab import drive
drive.mount('/content/drive')

import tensorflow as tf
print("GPU available:", tf.config.list_physical_devices('GPU'))


import os

DATA_DIR = '/content/drive/MyDrive/FloodShieldAI/data/sen1floods11'
os.makedirs(f'{DATA_DIR}/S1Hand', exist_ok=True)
os.makedirs(f'{DATA_DIR}/LabelHand', exist_ok=True)

# Public bucket -- no authentication needed for read access
!gsutil -m rsync -r gs://sen1floods11/v1.1/data/flood_events/HandLabeled/S1Hand {DATA_DIR}/S1Hand
!gsutil -m rsync -r gs://sen1floods11/v1.1/data/flood_events/HandLabeled/LabelHand {DATA_DIR}/LabelHand

s1_files = sorted(os.listdir(f'{DATA_DIR}/S1Hand'))
label_files = sorted(os.listdir(f'{DATA_DIR}/LabelHand'))
print(f"Downloaded {len(s1_files)} SAR chips and {len(label_files)} label chips")


import rasterio
import numpy as np

def load_chip(s1_path, label_path):
    with rasterio.open(s1_path) as src:
        img = src.read()  # shape (2, H, W) -- VV, VH
    with rasterio.open(label_path) as src:
        label = src.read(1)  # shape (H, W)
    return img, label

def normalize_sar(img):
    # SAR values are in dB, typically -50 to 0 -- clip and scale to 0-1
    img = np.clip(img, -50, 0)
    img = (img + 50) / 50.0
    return img

s1_paths = [f'{DATA_DIR}/S1Hand/{f}' for f in s1_files]
label_paths = [f'{DATA_DIR}/LabelHand/{f}' for f in label_files]

print("Sample chip check:")
img, label = load_chip(s1_paths[0], label_paths[0])
print("SAR image shape:", img.shape, "| Label shape:", label.shape)
print("Label unique values:", np.unique(label))


from tensorflow.image import resize as tf_resize

IMG_SIZE = 256

X_data, y_data = [], []

for s1_path, label_path in zip(s1_paths, label_paths):
    try:
        img, label = load_chip(s1_path, label_path)
        img = normalize_sar(img)                      # (2, H, W)
        img = np.transpose(img, (1, 2, 0))             # (H, W, 2)

        # skip chips that are mostly invalid (-1) labels
        valid_ratio = np.mean(label != -1)
        if valid_ratio < 0.5:
            continue

        label_clean = np.where(label == -1, 0, label)  # treat invalid as no-water for training

        img_resized = tf_resize(img, (IMG_SIZE, IMG_SIZE)).numpy()
        label_resized = tf_resize(label_clean[..., np.newaxis], (IMG_SIZE, IMG_SIZE), method='nearest').numpy()

        X_data.append(img_resized)
        y_data.append(label_resized)
    except Exception as e:
        continue

X_data = np.array(X_data, dtype=np.float32)
y_data = np.array(y_data, dtype=np.float32)

print("X_data:", X_data.shape, "| y_data:", y_data.shape)
print("Water pixel ratio:", y_data.mean())


from sklearn.model_selection import train_test_split

X_train, X_temp, y_train, y_temp = train_test_split(X_data, y_data, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)

print("Train:", X_train.shape, "Val:", X_val.shape, "Test:", X_test.shape)


from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, UpSampling2D, concatenate, BatchNormalization, Dropout

def conv_block(x, filters):
    x = Conv2D(filters, 3, padding='same', activation='relu')(x)
    x = BatchNormalization()(x)
    x = Conv2D(filters, 3, padding='same', activation='relu')(x)
    x = BatchNormalization()(x)
    return x

def build_unet(input_shape=(256,256,2)):
    inputs = Input(input_shape)

    c1 = conv_block(inputs, 32)
    p1 = MaxPooling2D()(c1)

    c2 = conv_block(p1, 64)
    p2 = MaxPooling2D()(c2)

    c3 = conv_block(p2, 128)
    p3 = MaxPooling2D()(c3)

    c4 = conv_block(p3, 256)
    p4 = MaxPooling2D()(c4)

    bn = conv_block(p4, 512)
    bn = Dropout(0.3)(bn)

    u4 = UpSampling2D()(bn)
    u4 = concatenate([u4, c4])
    c5 = conv_block(u4, 256)

    u3 = UpSampling2D()(c5)
    u3 = concatenate([u3, c3])
    c6 = conv_block(u3, 128)

    u2 = UpSampling2D()(c6)
    u2 = concatenate([u2, c2])
    c7 = conv_block(u2, 64)

    u1 = UpSampling2D()(c7)
    u1 = concatenate([u1, c1])
    c8 = conv_block(u1, 32)

    outputs = Conv2D(1, 1, activation='sigmoid')(c8)

    return Model(inputs, outputs)

unet_model = build_unet()
unet_model.summary()


def iou_metric(y_true, y_pred, smooth=1e-6):
    y_pred = tf.cast(y_pred > 0.5, tf.float32)
    intersection = tf.reduce_sum(y_true * y_pred)
    union = tf.reduce_sum(y_true) + tf.reduce_sum(y_pred) - intersection
    return (intersection + smooth) / (union + smooth)

unet_model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy', iou_metric]
)

from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

callbacks = [
    EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
    ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5)
]

history = unet_model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=40,
    batch_size=8,
    callbacks=callbacks,
    verbose=1
)


test_loss, test_acc, test_iou = unet_model.evaluate(X_test, y_test, verbose=0)
print(f"Test Accuracy: {test_acc:.4f}")
print(f"Test IoU (Intersection over Union): {test_iou:.4f}")

import matplotlib.pyplot as plt

plt.figure(figsize=(12,4))
plt.subplot(1,2,1)
plt.plot(history.history['loss'], label='train loss')
plt.plot(history.history['val_loss'], label='val loss')
plt.legend(); plt.title('Loss')

plt.subplot(1,2,2)
plt.plot(history.history['iou_metric'], label='train IoU')
plt.plot(history.history['val_iou_metric'], label='val IoU')
plt.legend(); plt.title('IoU')
plt.show()


n_show = 4
preds = unet_model.predict(X_test[:n_show])

fig, axes = plt.subplots(n_show, 3, figsize=(10, 3*n_show))
for i in range(n_show):
    axes[i,0].imshow(X_test[i][:,:,0], cmap='gray')
    axes[i,0].set_title('SAR Input (VV)')
    axes[i,1].imshow(y_test[i,:,:,0], cmap='Blues')
    axes[i,1].set_title('Ground Truth Flood Mask')
    axes[i,2].imshow(preds[i,:,:,0] > 0.5, cmap='Blues')
    axes[i,2].set_title('U-Net Prediction')
    for ax in axes[i]:
        ax.axis('off')
plt.tight_layout()
plt.show()


import os

SAVE_DIR = '/content/drive/MyDrive/FloodShieldAI/models'
os.makedirs(SAVE_DIR, exist_ok=True)

unet_model.save(f'{SAVE_DIR}/flood_segmentation_unet.keras')
print(f"✅ Saved to: {SAVE_DIR}/flood_segmentation_unet.keras")
