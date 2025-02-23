# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
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
"""Tests for SimpleRNN layer."""

import tensorflow.compat.v2 as tf

import copy

from absl.testing import parameterized
import numpy as np

import keras
from keras.testing_infra import test_combinations
from keras.testing_infra import test_utils


@test_combinations.generate(test_combinations.keras_mode_combinations())
class SimpleRNNLayerTest(tf.test.TestCase, parameterized.TestCase):
    def test_return_sequences_SimpleRNN(self):
        num_samples = 2
        timesteps = 3
        embedding_dim = 4
        units = 2
        test_utils.layer_test(
            keras.layers.SimpleRNN,
            kwargs={"units": units, "return_sequences": True},
            input_shape=(num_samples, timesteps, embedding_dim),
        )

    @test_utils.run_v2_only
    def test_float64_SimpleRNN(self):
        num_samples = 2
        timesteps = 3
        embedding_dim = 4
        units = 2
        test_utils.layer_test(
            keras.layers.SimpleRNN,
            kwargs={
                "units": units,
                "return_sequences": True,
                "dtype": "float64",
            },
            input_shape=(num_samples, timesteps, embedding_dim),
            input_dtype="float64",
        )

    def test_dynamic_behavior_SimpleRNN(self):
        num_samples = 2
        timesteps = 3
        embedding_dim = 4
        units = 2
        layer = keras.layers.SimpleRNN(units, input_shape=(None, embedding_dim))
        model = keras.models.Sequential()
        model.add(layer)
        model.compile("rmsprop", "mse")
        x = np.random.random((num_samples, timesteps, embedding_dim))
        y = np.random.random((num_samples, units))
        model.train_on_batch(x, y)

    def test_dropout_SimpleRNN(self):
        num_samples = 2
        timesteps = 3
        embedding_dim = 4
        units = 2
        test_utils.layer_test(
            keras.layers.SimpleRNN,
            kwargs={"units": units, "dropout": 0.1, "recurrent_dropout": 0.1},
            input_shape=(num_samples, timesteps, embedding_dim),
        )

    def test_implementation_mode_SimpleRNN(self):
        num_samples = 2
        timesteps = 3
        embedding_dim = 4
        units = 2
        for mode in [0, 1, 2]:
            test_utils.layer_test(
                keras.layers.SimpleRNN,
                kwargs={"units": units, "implementation": mode},
                input_shape=(num_samples, timesteps, embedding_dim),
            )

    def test_constraints_SimpleRNN(self):
        embedding_dim = 4
        layer_class = keras.layers.SimpleRNN
        k_constraint = keras.constraints.max_norm(0.01)
        r_constraint = keras.constraints.max_norm(0.01)
        b_constraint = keras.constraints.max_norm(0.01)
        layer = layer_class(
            5,
            return_sequences=False,
            weights=None,
            input_shape=(None, embedding_dim),
            kernel_constraint=k_constraint,
            recurrent_constraint=r_constraint,
            bias_constraint=b_constraint,
        )
        layer.build((None, None, embedding_dim))
        self.assertEqual(layer.cell.kernel.constraint, k_constraint)
        self.assertEqual(layer.cell.recurrent_kernel.constraint, r_constraint)
        self.assertEqual(layer.cell.bias.constraint, b_constraint)

    def test_with_masking_layer_SimpleRNN(self):
        layer_class = keras.layers.SimpleRNN
        inputs = np.random.random((2, 3, 4))
        targets = np.abs(np.random.random((2, 3, 5)))
        targets /= targets.sum(axis=-1, keepdims=True)
        model = keras.models.Sequential()
        model.add(keras.layers.Masking(input_shape=(3, 4)))
        model.add(layer_class(units=5, return_sequences=True, unroll=False))
        model.compile(loss="categorical_crossentropy", optimizer="rmsprop")
        model.fit(inputs, targets, epochs=1, batch_size=2, verbose=1)

    def test_from_config_SimpleRNN(self):
        layer_class = keras.layers.SimpleRNN
        for stateful in (False, True):
            l1 = layer_class(units=1, stateful=stateful)
            l2 = layer_class.from_config(l1.get_config())
            assert l1.get_config() == l2.get_config()

    def test_deep_copy_SimpleRNN(self):
        cell = keras.layers.SimpleRNNCell(5)
        copied_cell = copy.deepcopy(cell)
        self.assertEqual(copied_cell.units, 5)
        self.assertEqual(cell.get_config(), copied_cell.get_config())

    def test_regularizers_SimpleRNN(self):
        embedding_dim = 4
        layer_class = keras.layers.SimpleRNN
        layer = layer_class(
            5,
            return_sequences=False,
            weights=None,
            input_shape=(None, embedding_dim),
            kernel_regularizer=keras.regularizers.l1(0.01),
            recurrent_regularizer=keras.regularizers.l1(0.01),
            bias_regularizer="l2",
            activity_regularizer="l1",
        )
        layer.build((None, None, 2))
        self.assertLen(layer.losses, 3)

        x = keras.backend.variable(np.ones((2, 3, 2)))
        layer(x)
        if tf.executing_eagerly():
            self.assertLen(layer.losses, 4)
        else:
            self.assertLen(layer.get_losses_for(x), 1)

    def test_statefulness_SimpleRNN(self):
        num_samples = 2
        timesteps = 3
        embedding_dim = 4
        units = 2
        layer_class = keras.layers.SimpleRNN
        model = keras.models.Sequential()
        model.add(
            keras.layers.Embedding(
                4,
                embedding_dim,
                mask_zero=True,
                input_length=timesteps,
                batch_input_shape=(num_samples, timesteps),
            )
        )
        layer = layer_class(
            units, return_sequences=False, stateful=True, weights=None
        )
        model.add(layer)
        model.compile(
            optimizer=tf.compat.v1.train.GradientDescentOptimizer(0.01),
            loss="mse",
            run_eagerly=test_utils.should_run_eagerly(),
        )
        out1 = model.predict(np.ones((num_samples, timesteps)))
        self.assertEqual(out1.shape, (num_samples, units))

        # train once so that the states change
        model.train_on_batch(
            np.ones((num_samples, timesteps)), np.ones((num_samples, units))
        )
        out2 = model.predict(np.ones((num_samples, timesteps)))

        # if the state is not reset, output should be different
        self.assertNotEqual(out1.max(), out2.max())

        # check that output changes after states are reset
        # (even though the model itself didn't change)
        layer.reset_states()
        out3 = model.predict(np.ones((num_samples, timesteps)))
        self.assertNotEqual(out2.max(), out3.max())

        # check that container-level reset_states() works
        model.reset_states()
        out4 = model.predict(np.ones((num_samples, timesteps)))
        np.testing.assert_allclose(out3, out4, atol=1e-5)

        # check that the call to `predict` updated the states
        out5 = model.predict(np.ones((num_samples, timesteps)))
        self.assertNotEqual(out4.max(), out5.max())

        # Check masking
        layer.reset_states()

        left_padded_input = np.ones((num_samples, timesteps))
        left_padded_input[0, :1] = 0
        left_padded_input[1, :2] = 0
        out6 = model.predict(left_padded_input)

        layer.reset_states()

        right_padded_input = np.ones((num_samples, timesteps))
        right_padded_input[0, -1:] = 0
        right_padded_input[1, -2:] = 0
        out7 = model.predict(right_padded_input)

        np.testing.assert_allclose(out7, out6, atol=1e-5)

    def test_get_initial_states(self):
        batch_size = 4
        cell = keras.layers.SimpleRNNCell(20)
        initial_state = cell.get_initial_state(
            batch_size=batch_size, dtype=tf.float32
        )
        _, state = cell(
            np.ones((batch_size, 20), dtype=np.float32), initial_state
        )
        self.assertEqual(state.shape, initial_state.shape)


if __name__ == "__main__":
    tf.test.main()
