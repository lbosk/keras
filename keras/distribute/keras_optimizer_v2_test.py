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
"""Tests that show that DistributionStrategy works with optimizer v2."""

import tensorflow.compat.v2 as tf

from absl.testing import parameterized
import numpy as np

import keras
from keras.optimizers.optimizer_v2 import adam
from keras.optimizers.optimizer_v2 import gradient_descent


def get_model():
    x = keras.layers.Input(shape=(3,), name="input")
    y = keras.layers.Dense(4, name="dense")(x)
    model = keras.Model(x, y)
    return model


class MirroredStrategyOptimizerV2Test(tf.test.TestCase, parameterized.TestCase):
    @tf.__internal__.distribute.combinations.generate(
        tf.__internal__.test.combinations.combine(
            distribution=[
                tf.__internal__.distribute.combinations.central_storage_strategy_with_two_gpus,
            ],
            mode=["graph", "eager"],
        )
    )
    def testKerasOptimizerWithUnequalInput(self, distribution):
        with distribution.scope():
            var = tf.Variable(
                2.0, name="var", aggregation=tf.VariableAggregation.SUM
            )
            optimizer = adam.Adam(learning_rate=0.01, beta_1=0.2, beta_2=0.2)
            all_vars = []

            def model_fn():
                def loss_fn():
                    replica_id = _replica_id()
                    return tf.cast(replica_id + 1, dtype=tf.float32) * 0.5 * var

                train_op = optimizer.minimize(loss_fn, var_list=[var])

                return train_op, optimizer

            def train_fn():
                (
                    train_op,
                    optimizer,
                ) = distribution.extended.call_for_each_replica(model_fn)
                if not all_vars:
                    all_vars.append(var)
                    all_vars.append(optimizer.get_slot(var, "m"))
                    all_vars.append(optimizer.get_slot(var, "v"))
                return distribution.group(train_op)

            if not tf.executing_eagerly():
                with self.cached_session() as sess:
                    train_fn = sess.make_callable(train_fn())
            self.evaluate(tf.compat.v1.global_variables_initializer())

            # first step.
            train_fn()
            # var(1) = var(0) - lr * m(1) * sqrt(1 - beta2) / sqrt(v(1)) / (1 - beta1)
            #        = 2.0 - 0.01 * 1.2 * sqrt(0.8) / sqrt(1.8) / 0.8
            self.assertAllClose(1.99, self.evaluate(all_vars[0]))
            # m(1) = beta1 * m(0) + (1-beta1) * grad = 0.2 * 0 + 0.8 * (1 + 2) / 2
            self.assertAllClose(1.2, self.evaluate(all_vars[1]))
            # v(1) = beta2 * v(0) + (1-beta2) * grad^2 = 0.2 * 0 + 0.8 * 2.25
            self.assertAllClose(1.8, self.evaluate(all_vars[2]))

            # second step.
            train_fn()
            # var(1) = var(0) - lr * 2 = 1.98
            self.assertAllClose(1.98, self.evaluate(all_vars[0]))
            # m(2) = beta1 * m(1) + (1-beta1) * grad = 0.2 * 1.2 + 0.8 * 1.5
            self.assertAllClose(1.44, self.evaluate(all_vars[1]))
            # v(2) = beta2 * v(1) + (1-beta2) * grad^2 = 0.2 * 1.8 + 0.8 * 2.25
            self.assertAllClose(2.16, self.evaluate(all_vars[2]))

    @tf.__internal__.distribute.combinations.generate(
        tf.__internal__.test.combinations.combine(
            distribution=[
                tf.__internal__.distribute.combinations.central_storage_strategy_with_two_gpus,
            ],
            mode=["graph", "eager"],
        )
    )
    def testOptimizerWithKerasModelAndNumpyArrays(self, distribution):
        with self.cached_session():
            with distribution.scope():
                model = get_model()
                optimizer = gradient_descent.SGD(0.001)
                loss = "mse"
                metrics = ["mae"]
                model.compile(optimizer, loss, metrics=metrics)

            inputs = np.zeros((64, 3), dtype=np.float32)
            targets = np.zeros((64, 4), dtype=np.float32)

            model.fit(
                inputs,
                targets,
                epochs=1,
                batch_size=2,
                verbose=0,
                validation_data=(inputs, targets),
            )
            model.evaluate(inputs, targets)
            model.predict(inputs)


def _replica_id():
    replica_id = tf.distribute.get_replica_context().replica_id_in_sync_group
    if not isinstance(replica_id, tf.Tensor):
        replica_id = tf.constant(replica_id)
    return replica_id


if __name__ == "__main__":
    tf.test.main()
