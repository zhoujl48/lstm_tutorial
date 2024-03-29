#!/usr/bin/env python
# -*- coding:utf8 -*-
import collections
import os
import numpy as np
import argparse
import tensorflow as tf
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Embedding, Dropout, TimeDistributed, Dense, Activation
from tensorflow.keras.layers import LSTM
from tensorflow.keras.callbacks import ModelCheckpoint

data_path = 'tutorial_data'
parser = argparse.ArgumentParser()
parser.add_argument('run_opt', type=int, default=1, help='An integer:1 to train, 2 to test')
parser.add_argument('--data_path', type=str, default=data_path, help='The path of the training data')
args = parser.parse_args()
if args.data_path:
    data_path = args.data_path


def read_words(filename):
    with tf.gfile.GFile(filename, 'r') as f:
        return f.read().replace('\n', '<eos>').split()


def build_vocab(filename):
    """return: {word: index}"""
    data = read_words(filename)
    counter = collections.Counter(data)
    count_pairs = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    words, _ = list(zip(*count_pairs))
    word_to_id = dict(zip(words, range(len(words))))
    return word_to_id


def file_to_ids(filename, word_to_id):
    data = read_words(filename)
    return [word_to_id[word] for word in data if word in word_to_id]


def load_data():
    train_path = os.path.join(data_path, 'ptb.train.txt')
    valid_path = os.path.join(data_path, 'ptb.valid.txt')
    test_path = os.path.join(data_path, 'ptb.test.txt')

    word_to_id = build_vocab(train_path)
    train_data = file_to_ids(train_path, word_to_id)
    valid_data = file_to_ids(valid_path, word_to_id)
    test_data = file_to_ids(test_path, word_to_id)
    vocabulary = len(word_to_id)
    reversed_dictionary = dict(zip(word_to_id.values(), word_to_id.keys()))

    print(train_data[:5])
    print(vocabulary)
    print(' '.join(reversed_dictionary[x] for x in train_data[:10]))
    return train_data, valid_data, test_data, vocabulary, reversed_dictionary


train_data, valid_data, test_data, vocabulary, reversed_dictionary = load_data()


class KerasBatchGenerator(object):

    def __init__(self, data, num_steps, batch_size, vocabulary, skip_step=5):
        self.data = data
        self.num_steps = num_steps
        self.batch_size = batch_size
        self.vocabulary = vocabulary
        self.current_idx = 0
        self.skip_step = skip_step

    def generate(self):
        x = np.zeros((self.batch_size, self.num_steps))
        y = np.zeros((self.batch_size, self.num_steps, self.vocabulary))
        while True:
            for i in range(self.batch_size):
                if self.current_idx + self.num_steps >= len(self.data):
                    self.current_idx = 0
                x[i, :] = self.data[self.current_idx:self.current_idx + self.num_steps]
                temp_y = self.data[self.current_idx + 1:self.current_idx + self.num_steps + 1]
                y[i, :, :] = to_categorical(temp_y, num_classes=self.vocabulary)
                self.current_idx += self.skip_step
            yield x, y


num_steps = 30
batch_size = 20
train_data_generator = KerasBatchGenerator(train_data, num_steps, batch_size, vocabulary, skip_step=num_steps)
valid_data_generator = KerasBatchGenerator(valid_data, num_steps, batch_size, vocabulary, skip_step=num_steps)
hidden_size = 500
use_dropout = True

model = Sequential()
# Embedding: input = (batch_size, num_steps), output_size = (batch_size, num_steps, hidden_size)
model.add(Embedding(vocabulary, hidden_size, input_length=num_steps))
# return_sequences: return the full sequence(True) or the last output(Flase)
# return_sequences=Ture so we get num_steps sources(rather than 1) to correct errors
model.add(LSTM(hidden_size, return_sequences=True))
model.add(LSTM(hidden_size, return_sequences=True))
if use_dropout:
    model.add(Dropout(0.5))
model.add(TimeDistributed(Dense(vocabulary)))
model.add(Activation('softmax'))
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['categorical_accuracy'])
print(model.summary())

checkpointer = ModelCheckpoint(filepath=data_path + 'model/-{epoch:02d}.hdf5', verbose=1)
num_epochs = 50
if args.run_opt == 1:
    model.fit_generator(train_data_generator.generate(),
                        len(train_data) // (batch_size * num_steps), num_epochs,
                        validation_data=valid_data_generator.generate(),
                        validation_steps=len(valid_data) // (batch_size * num_steps),
                        callbacks=[checkpointer])
    model.save(os.path.join(data_path, 'final_model.hdf5'))
elif args.run_opt == 2:
    model = load_model(os.path.join(data_path, 'model-40.hdf5'))
    dummy_iters = 40
    example_training_generator = KerasBatchGenerator(train_data, num_steps, 1, vocabulary, skip_step=1)
    print('Training data:')
    for i in range(dummy_iters):
        dummy = next(example_training_generator.generate())
    num_predict = 10
    true_print_out = 'Actual words:'
    pred_print_out = 'Prediced words:'
    for i in range(num_predict):
        data = next(example_training_generator.generate())
        prediction = model.predict(data[0])
        predict_word = np.argmax(prediction[:, num_steps - 1, :])
        true_print_out += reversed_dictionary[train_data[num_steps + dummy_iters + i]] + ' '
        pred_print_out += reversed_dictionary[predict_word] + ' '
    print(true_print_out)
    print(pred_print_out)
    example_test_generator = KerasBatchGenerator(test_data, num_steps, 1, vocabulary,
                                                 skip_step=1)
    print("Test data:")
    for i in range(dummy_iters):
        dummy = next(example_test_generator.generate())
    num_predict = 10
    true_print_out = "Actual words: "
    pred_print_out = "Predicted words: "
    for i in range(num_predict):
        data = next(example_test_generator.generate())
        prediction = model.predict(data[0])
        predict_word = np.argmax(prediction[:, num_steps - 1, :])
        true_print_out += reversed_dictionary[test_data[num_steps + dummy_iters + i]] + " "
        pred_print_out += reversed_dictionary[predict_word] + " "
    print(true_print_out)
    print(pred_print_out)

