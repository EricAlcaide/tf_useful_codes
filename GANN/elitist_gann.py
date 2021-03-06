# -*- coding: utf-8 -*-

"""
	Code written entirely by Eric Alcaide: https://github.com/EricAlcaide

	Mimic biological reproduction in a darwinist environment.
	Elititst reproduction strategy, only the best ones survive
	plus a random additional to ensure genetic diversity.
	Attempt to create self-evolving, learning-based Neural Nets.

	ConvNets would perform much better, but it's not about accuracy.
"""

import keras
from keras.callbacks import EarlyStopping
from keras.datasets import cifar10
from keras.models import Sequential
from keras.optimizers import Optimizer
from keras.utils import np_utils
from keras.layers.core import Dense, Dropout
import logging
import numpy as np
from operator import add
import os
import random

# For reproducibility
np.random.seed(5)
# Record settings
LOG_FORMAT = "%(levelname)s %(asctime)s - %(message)s"
logging.basicConfig(filename=str(os.getcwd())+"/logging/elitist_log.txt",
					format = LOG_FORMAT,
					level = logging.DEBUG,
					filemode = "a")
logger = logging.getLogger()


# NN params object
class NetworkParams():
	def __init__(self, nb_layers, nb_neurons, activation, optimizer, dropout):
		self.params = { "nb_layers": nb_layers,
						"nb_neurons": nb_neurons,
						"activation": activation,
						"optimizer": optimizer,
						"dropout": dropout }

		self.acc_train = None
		self.acc_test = None


# Data preparation and verification
class DataPrep():
	def __init__(self):
		"""Retrieve the CIFAR dataset and process the data."""

		self.classes = ["airplane", "automobile ", "bird ", "cat" , "deer", "dog", "frog" , "horse", "ship", "truck"]
		self.nb_classes = 10
		self.batch_size = 64
		self.input_dim = 32*32*3
		self.nb_train = 50000
		self.nb_test = 10000
		# Get the data.
		(self.x_train, self.y_train), (self.x_test, self.y_test) = cifar10.load_data()
		# Preprocess it
		self.x_train = self.x_train.reshape(self.nb_train, self.input_dim)
		self.x_test = self.x_test.reshape(self.nb_test, self.input_dim)
		self.x_train = self.x_train.astype('float32')
		self.x_test = self.x_test.astype('float32')
		self.x_train /= 255
		self.x_test /= 255
		# convert class vectors to binary class matrices
		self.y_train = np_utils.to_categorical(self.y_train, self.nb_classes)
		self.y_test = np_utils.to_categorical(self.y_test, self.nb_classes)

		logger.info("Cifar10 data retrieved & Processed")


# Create the network from params set and train it
class Network():
	def __init__(self, data, net):
		self.data = data
		params = net.params
		model = Sequential()
		# Add each layer.
		for i in range(params['nb_layers']):
			# Need input dim for first layer.
			if i == 0:
				model.add(Dense(params['nb_neurons'], activation=params['activation'], input_dim = data.input_dim))
			else:
				model.add(Dense(params['nb_neurons'], activation=params['activation']))

			model.add(Dropout(params['dropout']))

		# Output layer.
		model.add(Dense(self.data.nb_classes, activation='softmax'))
		model.compile(loss='categorical_crossentropy', optimizer=params['optimizer'], metrics=['accuracy'])
		self.model = model

	def train(self):
		"""Train the model, return test accuracy."""
		# Helper: Early stopping.
		early_stop = EarlyStopping(patience=5, verbose = 1)
		self.model.fit(self.data.x_train, self.data.y_train,
						batch_size=self.data.batch_size,
						epochs=10000,  # using early stopping, so no real limit
						verbose=1,
						validation_split=0.05,
						callbacks=[early_stop])

		score = self.model.evaluate(self.data.x_test, self.data.y_test, verbose=1)

		return score[1]  # return accuracy. [0] is loss.


# Genetic Algorithm stuff
class Genetic():
	def __init__(self):
		self.data = DataPrep()

		self.n_nets = 20
		self.n_iter = 10
		self.retain = 0.2
		self.retain_length = int(self.retain*self.n_nets)
		self.mutation = 0.1
		self.random_add = 0.05
		self.eval_history = [0]	

		self.nb_layers = [1,2,3,4,5]
		self.nb_neurons = [32,64,128,256,512,768,1024]
		self.activation = ['tanh', 'sigmoid', 'relu', 'elu', 'selu', 'linear']
		self.optimizer = ['sgd', 'adamax', 'rmsprop', 'adagrad', 'adadelta', 'adam', 'nadam']
		self.dropout = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4]
	
		self.params = { "nb_layers": self.nb_layers,
						"nb_neurons": self.nb_neurons,
						"activation": self.activation,
						"optimizer": self.optimizer,
						"dropout": self.dropout }

	# Create the population here
	def generation(self):
		return [ NetworkParams(
					self.nb_layers[np.random.randint(len(self.nb_layers))],
					self.nb_neurons[np.random.randint(len(self.nb_neurons))],
					self.activation[np.random.randint(len(self.activation))],
					self.optimizer[np.random.randint(len(self.optimizer))],
					self.dropout[np.random.randint(len(self.dropout))]
				) for n in range(self.n_nets) ]

	# Measure the fitness of an entire population. Lower is better.
	def evaluate(self, population):
		tests = np.array([nn.acc_test*100 for nn in population])
		total = np.sum(tests, axis=0)
		return total / float(self.n_nets)

	# Generate a child and then randomly replace all genes for the ones coming either from male or female	
	def breed(self, male, female):
		child = NetworkParams(None, None, None, None, None)
		for key in child.params:
			child.params[key] = random.choice(
				[male.params[key], female.params[key]]
			)
		return child

	# Evolve individuals and create the next generation. Select the 20% best +  random %. Elitist Reproduction.
	def evolve(self, population):
		self.train(population)
		# Select the best individuals
		tupled = [ nn for nn in sorted(population, key=lambda x: x.acc_test, reverse=True)]
		parents = tupled[:self.retain_length]
		# Select other individuals randomly to maintain genetic diversity.
		for nn in tupled[self.retain_length:]:
			if self.random_add > np.random.random():
				parents.append(nn)
		# Record the selected parents
		logger.info("Parents: {0}".format(str([nn.params for nn in parents])))
		logger.info("*************************************************")
		# Mutate some individuals to maintain genetic diversity
		for nn in parents:
			for key in self.params:
				if self.mutation > np.random.random():
					nn.params[key] = random.choice(self.params[key])
		# Crossover of parents to generate children
		parents_length = len(parents)
		children_maxlength = self.n_nets - parents_length
		children = []
		while len(children) < children_maxlength:
			male = np.random.randint(0, parents_length)
			female = np.random.randint(0, parents_length)
			if male != female:
				# Combine male and female
				child = self.breed(parents[male], parents[female])			
				children.append(child)
		# Extend parents list by appending children list
		parents.extend(children)	
		# Return the next Generation of individuals
		return parents

	# Train every single NN in the population
	def train(self, population):
		for nn in population:
			logger.info("Saving the accuracy result of the training")
			logger.info("Number of layers: {0}".format(nn.params['nb_layers']))
			logger.info("Number of neurons: {0}".format(nn.params['nb_neurons']))
			logger.info("Activation: {0}".format(nn.params['activation']))
			logger.info("Optimizer: {0}".format(nn.params['optimizer']))
			logger.info("Dropout: {0}".format(nn.params['dropout']))
			# Train Network
			nn.acc_test = Network(self.data, nn).train()
			
			# Log the result
			logger.info("Acc @ Testing: {0}%".format(nn.acc_test*100)+"%")
			logger.info("--------------------------------------------------------")
			# Free space
			self.free_gpu_mem()

		avg_acc = self.evaluate(population)
		self.eval_history.append(avg_acc)
		logger.info("Generation Average: {0}%".format(avg_acc))
		logger.info("--------------------------------------------------------")

	def free_gpu_mem(self):
		# Free gpu space
		keras.backend.get_session().close()
		keras.backend.set_session(keras.backend.tf.Session())


if __name__ == "__main__":
	gen = Genetic()
	
	# Run the Genetic Algorithm and let Nets Evolve
	pop = gen.generation()

	for i in range(0,gen.n_iter):
		logger.info("------ GEN {0}".format(i+1)+" ------")
		pop = gen.evolve(pop)

	# Record final information
	logger.info("/////////////////////////////////////////////////////")
	logger.info("/////////////////////////////////////////////////////")
	logger.info(str(gen.eval_history))