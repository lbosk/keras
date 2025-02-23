# Copyright 2018 The TensorFlow Authors. All Rights Reserved.
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
"""Tests for Model subclassing."""

import tensorflow.compat.v2 as tf

import copy
import os

from absl.testing import parameterized
import numpy as np

import keras
from tensorflow.python.framework import (
    test_util as tf_test_utils,
)
from keras.testing_infra import test_combinations
from keras.testing_infra import test_utils
from keras.tests import model_subclassing_test_util as model_util
from tensorflow.python.training.tracking import (
    data_structures,
)

try:
    import h5py  # pylint:disable=g-import-not-at-top
except ImportError:
    h5py = None


@test_combinations.run_all_keras_modes
class ModelSubclassingTest(test_combinations.TestCase):
    def test_custom_build(self):
        class DummyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.dense1 = keras.layers.Dense(32, activation="relu")
                self.uses_custom_build = False

            def call(self, inputs):
                return self.dense1(inputs)

            def build(self, input_shape):
                self.uses_custom_build = True

        test_model = DummyModel()
        dummy_data = tf.ones((32, 50))
        test_model(dummy_data)
        self.assertTrue(
            test_model.uses_custom_build,
            "Model should use user " "defined build when called.",
        )

    def test_attribute_conflict_error(self):
        class ModelWithProperty(keras.Model):
            @property
            def read_only(self):
                return 1.0

        m = ModelWithProperty()
        with self.assertRaisesRegex(AttributeError, "read_only"):
            m.read_only = 2.0

    def test_custom_build_with_fit(self):
        class DummyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.layer1 = keras.layers.Dense(10, activation="relu")

            def build(self, input_shape):
                self.layer2 = keras.layers.Dense(1, activation="relu")

            def call(self, inputs):
                return self.layer2(self.layer1(inputs))

        model = DummyModel()
        model.compile("sgd", "mse", run_eagerly=test_utils.should_run_eagerly())
        model.fit(np.ones((10, 10)), np.ones((10, 1)), batch_size=2, epochs=2)
        self.assertLen(model.layers, 2)
        self.assertLen(model.trainable_variables, 4)

    def test_dataset_dict_with_fit(self):
        class MyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.dense1 = keras.layers.Dense(1)
                self.dense2 = keras.layers.Dense(1)
                self.add = keras.layers.Add()

            def call(self, x):
                return self.add([self.dense1(x["a"]), self.dense2(x["b"])])

        model = MyModel()
        model.compile("sgd", "mse", run_eagerly=test_utils.should_run_eagerly())

        data = tf.data.Dataset.from_tensor_slices(
            ({"a": np.ones((32, 10)), "b": np.ones((32, 20))}, np.ones((32, 1)))
        ).batch(2)
        model.fit(data, epochs=2)

    def test_invalid_input_shape_build(self):
        num_classes = 2
        input_dim = 50

        model = test_utils.SmallSubclassMLP(
            num_hidden=32, num_classes=num_classes, use_dp=True, use_bn=True
        )

        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        with self.assertRaisesRegex(
            ValueError, "input shape is not one of the valid types"
        ):
            model.build(input_shape=tf.compat.v1.Dimension(input_dim))

    def test_embed_dtype_with_subclass_build(self):
        class Embedding(keras.layers.Layer):
            """An Embedding layer."""

            def __init__(self, vocab_size, embedding_dim, **kwargs):
                super().__init__(**kwargs)
                self.vocab_size = vocab_size
                self.embedding_dim = embedding_dim

            def build(self, _):
                self.embedding = self.add_weight(
                    "embedding_kernel",
                    shape=[self.vocab_size, self.embedding_dim],
                    dtype=np.float32,
                    initializer=tf.compat.v1.random_uniform_initializer(
                        -0.1, 0.1
                    ),
                    trainable=True,
                )

            def call(self, x):
                return tf.compat.v1.nn.embedding_lookup(self.embedding, x)

        class EmbedModel(keras.Model):
            def __init__(self, vocab_size, embed_size):
                super().__init__()
                self.embed1 = Embedding(vocab_size, embed_size)

            def call(self, inputs):
                return self.embed1(inputs)

        model = EmbedModel(100, 20)
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        with self.assertRaisesRegex(
            ValueError, "if your layers do not support float type inputs"
        ):
            model.build(input_shape=(35, 20))

    def test_single_time_step_rnn_build(self):
        dim = 4
        timesteps = 1
        batch_input_shape = (None, timesteps, dim)
        units = 3

        class SimpleRNNModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.lstm = keras.layers.LSTM(units)

            def call(self, inputs):
                return self.lstm(inputs)

        model = SimpleRNNModel()
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build(batch_input_shape)
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )
        model(tf.ones((32, timesteps, dim)))

    def test_single_io_subclass_build(self):
        num_classes = 2
        input_dim = 50
        batch_size = None

        model = test_utils.SmallSubclassMLP(
            num_hidden=32, num_classes=num_classes, use_dp=True, use_bn=True
        )

        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build(input_shape=(batch_size, input_dim))
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )
        model(tf.ones((32, input_dim)))

    def test_single_io_dimension_subclass_build(self):
        num_classes = 2
        input_dim = tf.compat.v1.Dimension(50)
        batch_size = tf.compat.v1.Dimension(None)

        model = test_utils.SmallSubclassMLP(
            num_hidden=32, num_classes=num_classes, use_dp=True, use_bn=True
        )

        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build(input_shape=(batch_size, input_dim))
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )
        model(tf.ones((32, input_dim)))

    def test_multidim_io_subclass_build(self):
        num_classes = 10
        # Input size, e.g. image
        batch_size = 32
        input_shape = (32, 32, 3)

        model = model_util.SimpleConvTestModel(num_classes)
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        batch_input_shape = (batch_size,) + input_shape
        model.build(input_shape=batch_input_shape)
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )

        model(tf.ones(batch_input_shape))

    def test_tensorshape_io_subclass_build(self):
        num_classes = 10
        # Input size, e.g. image
        batch_size = None
        input_shape = (32, 32, 3)

        model = model_util.SimpleConvTestModel(num_classes)
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build(input_shape=tf.TensorShape((batch_size,) + input_shape))
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )

        model(tf.ones((32,) + input_shape))

    def test_subclass_save_model(self):
        num_classes = 10
        # Input size, e.g. image
        batch_size = None
        input_shape = (32, 32, 3)

        model = model_util.SimpleConvTestModel(num_classes)
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build(input_shape=tf.TensorShape((batch_size,) + input_shape))
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )
        weights = model.get_weights()

        tf_format_name = os.path.join(self.get_temp_dir(), "ckpt")
        model.save_weights(tf_format_name)
        if h5py is not None:
            hdf5_format_name = os.path.join(self.get_temp_dir(), "weights.h5")
            model.save_weights(hdf5_format_name)

        model = model_util.SimpleConvTestModel(num_classes)
        model.build(input_shape=tf.TensorShape((batch_size,) + input_shape))
        if h5py is not None:
            model.load_weights(hdf5_format_name)
            self.assertAllClose(weights, model.get_weights())
        model.load_weights(tf_format_name)
        self.assertAllClose(weights, model.get_weights())

    def test_multi_io_subclass_build(self):
        batch_size = None
        num_samples = 1000
        input_dim = 50
        model = model_util.get_multi_io_subclass_model()
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        batch_input_shape = tf.TensorShape((batch_size, input_dim))
        model.build(input_shape=[batch_input_shape, batch_input_shape])
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )
        x1 = tf.ones((num_samples, input_dim))
        x2 = tf.ones((num_samples, input_dim))
        model([x1, x2])

    def test_summary(self):
        class ToString:
            def __init__(self):
                self.contents = ""

            def __call__(self, msg):
                self.contents += msg + "\n"

        # Single-io
        model = test_utils.SmallSubclassMLP(
            num_hidden=32, num_classes=4, use_bn=True, use_dp=True
        )
        model(np.ones((3, 4)))  # need to build model first
        print_fn = ToString()
        model.summary(print_fn=print_fn)
        self.assertIn("Trainable params: 356", print_fn.contents)

        # Multi-io
        model = model_util.get_multi_io_subclass_model(
            num_classes=(5, 6), use_bn=True, use_dp=True
        )
        model([np.ones((3, 4)), np.ones((3, 4))])  # need to build model first
        print_fn = ToString()
        model.summary(print_fn=print_fn)
        self.assertIn("Trainable params: 587", print_fn.contents)

        # Single-io with unused layer
        model = test_utils.SmallSubclassMLP(
            num_hidden=32, num_classes=4, use_bn=True, use_dp=True
        )
        model.unused_layer = keras.layers.Dense(10)
        model(np.ones((3, 4)))  # need to build model first
        print_fn = ToString()
        model.summary(print_fn=print_fn)
        self.assertIn("Trainable params: 356", print_fn.contents)
        self.assertIn("0 (unused)", print_fn.contents)

    def test_no_dependency(self):
        class Foo(keras.Model):
            def __init__(self):
                super().__init__()
                self.isdep = keras.layers.Dense(1)
                self.notdep = data_structures.NoDependency(
                    keras.layers.Dense(2)
                )
                self.notdep_var = data_structures.NoDependency(
                    tf.Variable(1.0, name="notdep_var")
                )

        m = Foo()
        self.assertEqual([m.isdep, m.notdep], m.layers)
        self.assertEqual(1, len(m._trackable_children()))
        self.assertIs(m.isdep, m._trackable_children()["isdep"])
        self.assertEqual("notdep_var:0", m.notdep_var.name)

    def test_extra_variable(self):
        class ExtraVar(keras.Model):
            def __init__(self):
                super().__init__()
                self.dense = keras.layers.Dense(1)
                self.var = tf.Variable(1.0)
                self.not_trainable_var = tf.Variable(2.0, trainable=False)

            def call(self, inputs):
                return self.dense(inputs + self.var)

        m = ExtraVar()
        self.assertTrue(m.trainable)
        self.assertEqual([m.dense], m.layers)
        self.assertEqual([m.var, m.not_trainable_var], m.variables)
        self.assertEqual([m.var], m.trainable_variables)
        self.assertEqual([m.not_trainable_var], m.non_trainable_variables)
        self.assertLen(m.get_weights(), 2)
        m.trainable = False
        self.assertEqual([m.var, m.not_trainable_var], m.variables)
        self.assertEqual([], m.trainable_variables)
        self.assertEqual(
            [m.var, m.not_trainable_var], m.non_trainable_variables
        )
        self.assertLen(m.get_weights(), 2)
        m.trainable = True

        m(tf.ones([1, 1]))

        self.assertEqual([m.dense.kernel, m.dense.bias], m.dense.variables)
        self.assertEqual([m.dense.kernel, m.dense.bias], m.dense.weights)

        self.assertLen(m.get_weights(), 4)
        self.assertEqual(
            [m.dense.kernel, m.dense.bias, m.var, m.not_trainable_var],
            m.variables,
        )
        self.assertEqual(
            [m.dense.kernel, m.dense.bias, m.var], m.trainable_variables
        )
        self.assertEqual([m.not_trainable_var], m.non_trainable_variables)

        m.dense.trainable = False
        self.assertEqual(
            [m.dense.kernel, m.dense.bias, m.var, m.not_trainable_var],
            m.variables,
        )
        self.assertEqual([m.var], m.trainable_variables)
        self.assertEqual(
            [m.dense.kernel, m.dense.bias, m.not_trainable_var],
            m.non_trainable_variables,
        )
        self.assertLen(m.get_weights(), 4)

    def test_add_weight_in_model(self):
        class MyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.b = self.add_weight("bias", (10,))
                self.c = self.add_weight("bias2", (10,), trainable=False)

            def call(self, inputs):
                return inputs + self.b + self.c

        x = tf.convert_to_tensor(np.ones((10, 10), "float32"))
        model = MyModel()
        model(x)
        self.assertEqual(1, len(model.trainable_weights))
        self.assertEqual(1, len(model.non_trainable_weights))
        self.assertEqual(2, len(model.weights))

        class MyModelCustomBuild(keras.Model):
            def build(self, input_shape):
                self.b = self.add_weight("bias", (10,))
                self.c = self.add_weight("bias2", (10,), trainable=False)

            def call(self, inputs):
                return inputs + self.b + self.c

        x = tf.convert_to_tensor(np.ones((10, 10), "float32"))
        model = MyModelCustomBuild()
        model(x)
        self.assertEqual(1, len(model.trainable_weights))
        self.assertEqual(1, len(model.non_trainable_weights))
        self.assertEqual(2, len(model.weights))

    def test_add_update_in_model(self):
        class MyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.b = self.add_weight("bias", (10,))
                self.c = self.add_weight("bias2", (10,))

            def call(self, inputs):
                # Unconditional
                self.add_update(self.b.assign(self.b * 2))
                # Conditional
                self.add_update(self.c.assign(inputs[1, :]))
                return inputs + self.b + self.c

        x = tf.convert_to_tensor(np.ones((10, 10), "float32"))
        model = MyModel()
        model(x)

        if tf.executing_eagerly():
            self.assertEqual(0, len(model.updates))
        else:
            self.assertEqual(2, len(model.updates))


class GraphSpecificModelSubclassingTests(tf.test.TestCase):
    def test_single_io_workflow_with_tensors(self):
        num_classes = 2
        num_samples = 10
        input_dim = 50

        with tf.Graph().as_default(), self.cached_session():
            model = test_utils.SmallSubclassMLP(
                num_hidden=32, num_classes=num_classes, use_dp=True, use_bn=True
            )
            model.compile(loss="mse", optimizer="rmsprop")

            x = tf.ones((num_samples, input_dim))
            y = tf.zeros((num_samples, num_classes))

            model.fit(x, y, epochs=2, steps_per_epoch=10, verbose=0)
            _ = model.evaluate(steps=10, verbose=0)

    def test_multi_io_workflow_with_tensors(self):
        num_classes = (2, 3)
        num_samples = 10
        input_dim = 50

        with tf.Graph().as_default(), self.cached_session():
            model = model_util.get_multi_io_subclass_model(
                num_classes=num_classes, use_dp=True, use_bn=True
            )
            model.compile(loss="mse", optimizer="rmsprop")

            x1 = tf.ones((num_samples, input_dim))
            x2 = tf.ones((num_samples, input_dim))
            y1 = tf.zeros((num_samples, num_classes[0]))
            y2 = tf.zeros((num_samples, num_classes[1]))

            model.fit(
                [x1, x2], [y1, y2], epochs=2, steps_per_epoch=10, verbose=0
            )
            _ = model.evaluate(steps=10, verbose=0)

    def test_updates_and_losses_for_nested_models_in_subclassed_model(self):

        # Case 1: deferred-build sequential nested in subclass.
        class TestModel1(keras.Model):
            def __init__(self):
                super().__init__()
                self.fc = keras.layers.Dense(
                    10, input_shape=(784,), activity_regularizer="l1"
                )
                self.bn = keras.Sequential(
                    [keras.layers.BatchNormalization(axis=1)]
                )

            def call(self, x):
                return self.bn(self.fc(x))

        with tf.compat.v1.get_default_graph().as_default(), self.cached_session():
            model = TestModel1()

            x = tf.ones(shape=[100, 784], dtype="float32")
            model(x)
            self.assertLen(model.updates, 2)
            self.assertLen(model.losses, 1)

        # Case 2: placeholder-sequential nested in subclass.
        class TestModel2(keras.Model):
            def __init__(self):
                super().__init__()
                self.fc = keras.layers.Dense(
                    10, input_shape=(784,), activity_regularizer="l1"
                )
                self.bn = keras.Sequential(
                    [keras.layers.BatchNormalization(axis=1, input_shape=(10,))]
                )

            def call(self, x):
                return self.bn(self.fc(x))

        with tf.compat.v1.get_default_graph().as_default(), self.cached_session():
            model = TestModel2()

            x = tf.ones(shape=[100, 784], dtype="float32")
            model(x)
            self.assertEqual(len(model.get_updates_for(x)), 2)
            self.assertEqual(len(model.get_losses_for(x)), 1)

        # Case 3: functional-API model nested in subclass.
        with tf.compat.v1.get_default_graph().as_default():
            inputs = keras.Input((10,))
            outputs = keras.layers.BatchNormalization(axis=1)(inputs)
            bn = keras.Model(inputs, outputs)

            class TestModel3(keras.Model):
                def __init__(self):
                    super().__init__()
                    self.fc = keras.layers.Dense(
                        10, input_shape=(784,), activity_regularizer="l1"
                    )
                    self.bn = bn

                def call(self, x):
                    return self.bn(self.fc(x))

            with self.cached_session():
                model = TestModel3()

                x = tf.ones(shape=[100, 784], dtype="float32")
                model(x)
                self.assertEqual(len(model.get_updates_for(x)), 2)
                self.assertEqual(len(model.get_losses_for(x)), 1)

    def test_multi_io_workflow_with_numpy_arrays_and_custom_placeholders(self):
        num_classes = (2, 3)
        num_samples = 1000
        input_dim = 50

        with tf.Graph().as_default(), self.cached_session():
            model = model_util.get_multi_io_subclass_model(
                num_classes=num_classes, use_dp=True, use_bn=True
            )
            model.compile(loss="mse", optimizer="rmsprop")

            x1 = np.ones((num_samples, input_dim))
            x2 = np.ones((num_samples, input_dim))
            y1 = np.zeros((num_samples, num_classes[0]))
            y2 = np.zeros((num_samples, num_classes[1]))

            x2_placeholder = tf.compat.v1.placeholder(
                dtype="float32", shape=(None, input_dim)
            )
            model._set_inputs([x1, x2_placeholder])

            model.fit([x1, x2], [y1, y2], epochs=2, batch_size=32, verbose=0)
            _ = model.evaluate([x1, x2], [y1, y2], verbose=0)


@test_combinations.generate(test_combinations.combine(mode=["graph", "eager"]))
class CustomCallSignatureTests(tf.test.TestCase, parameterized.TestCase):
    def test_no_inputs_in_signature(self):
        model = model_util.CustomCallModel()
        first = tf.ones([2, 3])
        second = tf.ones([2, 5])
        output = model(first, second)
        self.evaluate([v.initializer for v in model.variables])
        expected_output = self.evaluate(
            model.dense1(first) + model.dense2(second)
        )
        self.assertAllClose(expected_output, self.evaluate(output))
        output = model(first, second, fiddle_with_output="yes")
        self.assertAllClose(10.0 * expected_output, self.evaluate(output))
        output = model(first, second=second, training=False)
        self.assertAllClose(expected_output, self.evaluate(output))

    def test_training_args_call_build(self):
        input_dim = 2

        model = model_util.TrainingNoDefaultModel()
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build((None, input_dim))
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )

    def test_training_and_mask_args_call_build(self):
        input_dim = 2

        model = model_util.TrainingMaskingModel()
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        model.build((None, input_dim))
        self.assertTrue(
            model.weights,
            (
                "Model should have weights now that it "
                "has been properly built."
            ),
        )
        self.assertTrue(
            model.built, "Model should be built after calling `build`."
        )

    def test_custom_call_kwargs_and_build(self):
        first_input_shape = (2, 3)
        second_input_shape = (2, 5)

        model = model_util.CustomCallModel()
        self.assertFalse(model.built, "Model should not have been built")
        self.assertFalse(
            model.weights,
            ("Model should have no weights since it " "has not been built."),
        )
        with self.assertRaisesRegex(
            ValueError, "cannot build your model if it has positional"
        ):
            model.build(input_shape=[first_input_shape, second_input_shape])

    def test_kwargs_in_signature(self):
        class HasKwargs(keras.Model):
            def call(self, x, y=3, **kwargs):
                return x

        model = HasKwargs()
        arg = tf.ones([1])
        model(arg, a=3)
        if not tf.executing_eagerly():
            self.assertLen(model.inputs, 1)

    @tf_test_utils.assert_no_new_tensors
    @tf_test_utils.assert_no_garbage_created
    def test_training_no_default(self):
        if not tf.executing_eagerly():
            return
        model = model_util.TrainingNoDefaultModel()
        arg = tf.ones([1, 1])
        model(arg, True)

    def test_positional_arg_in_call(self):
        class ModelWithPositionalArgs(keras.Model):
            def call(self, x, x2, x3=None):
                return x + x2

        x = np.ones((10, 1))
        y = np.ones((10, 1))
        m = ModelWithPositionalArgs()
        m.compile("sgd", "mse")
        with self.assertRaisesRegex(ValueError, r"Models passed to `fit`"):
            m.fit(x, y, batch_size=2)
        with self.assertRaisesRegex(ValueError, r"Models passed to `evaluate`"):
            m.evaluate(x, y, batch_size=2)
        with self.assertRaisesRegex(ValueError, r"Models passed to `predict`"):
            m.predict(x, batch_size=2)
        with self.assertRaisesRegex(
            ValueError, r"Models passed to `train_on_batch`"
        ):
            m.train_on_batch(x, y)
        with self.assertRaisesRegex(
            ValueError, r"Models passed to `test_on_batch`"
        ):
            m.test_on_batch(x, y)
        with self.assertRaisesRegex(
            ValueError, r"Models passed to `predict_on_batch`"
        ):
            m.predict_on_batch(x)

    def test_deepcopy(self):
        if not tf.executing_eagerly():
            self.skipTest("Run in eager mode only.")

        class MyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.my_variable = tf.Variable(0.0, trainable=False)
                self.layer = keras.layers.Dense(4)

            def call(self, obs):
                return self.layer(obs)

        model = MyModel()
        model.my_variable.assign_add(1.0)

        new_model = copy.deepcopy(model)
        self.assertEqual(model.my_variable.numpy(), 1.0)
        self.assertEqual(new_model.my_variable.numpy(), 1.0)

        model.my_variable.assign_add(1.0)
        self.assertEqual(model.my_variable.numpy(), 2.0)
        self.assertEqual(new_model.my_variable.numpy(), 1.0)

        # Check that Trackable logic still works.
        self.assertLen(new_model.variables, 1)
        self.assertLen(new_model.layers, 1)

    def test_batch_counters_not_in_variables(self):
        class MyModel(keras.Model):
            def __init__(self):
                super().__init__()
                self.layer = keras.layers.Dense(4)

            def call(self, obs):
                return self.layer(obs)

        model = MyModel()
        model(np.ones((10, 10)))
        self.assertLen(model.variables, 2)


if __name__ == "__main__":
    tf.test.main()
