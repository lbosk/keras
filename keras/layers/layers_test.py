# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# pylint: disable=g-classes-have-attributes
"""Tests for layers.__init__."""

from keras import layers
import tensorflow.compat.v2 as tf


class LayersTest(tf.test.TestCase):
    def test_keras_private_symbol(self):
        normalization_parent = layers.BatchNormalization.__module__.split(".")[
            -1
        ]
        if tf.__internal__.tf2.enabled():
            self.assertEqual("batch_normalization", normalization_parent)
            self.assertTrue(layers.BatchNormalization._USE_V2_BEHAVIOR)
        else:
            self.assertEqual("batch_normalization_v1", normalization_parent)
            self.assertFalse(layers.BatchNormalization._USE_V2_BEHAVIOR)


if __name__ == "__main__":
    tf.test.main()
