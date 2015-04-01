#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import json
import os
from os import listdir
from os.path import isdir, isfile, join
import networkx as nx
import networkxgmml
from parse_xgmml import Parse_XGMML
from parse_bridgedb_datasources import Parse_BridgeDb_Datasources
import re
import regexes

def get_file_paths(filelike_object, file_extension):
    if hasattr(filelike_object, 'name'):
        return filelike_object.name
    else:
        source_xgmml_file_paths = []
        if os.path.isdir(filelike_object):
            source_xgmml_file_paths += [ filelike_object + f for f in listdir(filelike_object) if isfile(join(filelike_object,f)) and has_file_extension(f, file_extension) ]
        elif os.path.isfile(filelike_object):
            source_xgmml_file_paths += [ filelike_object ]
        else:
            print filelike_object
            raise ValueError('File or directory input error.')

        return source_xgmml_file_paths


def has_file_extension(filename, file_extension):
    expected_index = len(filename) - len(file_extension)
    return filename.find(file_extension, expected_index, len(filename)) == expected_index


def has_matching_node(current_mapping_graph, node_id):
    verified_node_id = None
    if current_mapping_graph.has_node(node_id):
        verified_node_id = node_id
    else:
        for onenode in current_mapping_graph.nodes():
            current_node = current_mapping_graph.node[onenode]
            if ((('identifiers' in current_node) and (node_id in current_node['identifiers'])) or (('@label' in current_node) and (node_id == current_node['@label'])) or (('label' in current_node) and (node_id == current_node['label'])) or (('mimat id' in current_node) and (node_id == current_node['mimat id'])) or (('name' in current_node) and (node_id == current_node['name']))):
                if (('mimat id' in current_node) and (node_id == current_node['mimat id'])):
                    verified_node_id = onenode
                    break
                elif (('identifiers' in current_node) and (node_id in current_node['identifiers'])):
                    verified_node_id = onenode
                elif not verified_node_id:
                    verified_node_id = onenode
    return verified_node_id


def TargetInteractionFinder(source_xgmml, node_id_list_file_path=None, node_id_list_column_index=0, output_dir='./'):
    results_file_path = output_dir + 'interactions.csv'
    results_file = open(results_file_path, 'w')
    results_file.write('queryid,targetid,score,pvalue,pmid,datasource\n')
    results_file.close()

    logfile_path = output_dir + 'summary.log'
    open(logfile_path, 'w').close()

    log_result = dict()
    log_result['total_result_count'] = 0
    log_result['skipped_count'] = 0
    log_result['results_by_source'] = {}

    file_extension = '.xgmml'
    source_xgmml_file_paths = []
    if hasattr(source_xgmml, '__iter__'):
        for source_xgmml_filelike_object in source_xgmml:
            source_xgmml_file_paths += get_file_paths(source_xgmml_filelike_object, file_extension)
    else:
        source_xgmml_file_paths += get_file_paths(source_xgmml, file_extension)

    print 'source_xgmml_file_paths'
    print source_xgmml_file_paths

    versions = []

    node_id_list = []
    with open(node_id_list_file_path, 'rb') as csvfile:
        node_id_list_reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
        for row in node_id_list_reader:
            node_id_list.append(row[node_id_list_column_index])

    log_result['query_count'] = len(node_id_list)

    for source_xgmml_file_path in source_xgmml_file_paths:
        source_xgmml_file_path_components = source_xgmml_file_path.split('/')
        version = source_xgmml_file_path_components[len(source_xgmml_file_path_components) - 1].replace('.xgmml', '')
        versions.append(version)

        current_mapping_graph = Parse_XGMML(source_xgmml_file_path)
        log_result[version + '_result_count'] = 0

        datasource_subgraph_node_ids = []

        id_mappings={}

        for node_id in node_id_list:
            verified_node_id = None
            name_or_identifier = None
            if not node_id:
                print 'Warning: No name (e.g., hsa-miR-542-3p), identifier (e.g., MIMAT0003389) or IRI (e.g., http://identifiers.org/mirbase.mature/MIMAT0003389) provided.'
                log_result['skipped_count'] += 1
                break

            if regexes.identifiers_org.match(node_id):
                name_or_identifier = re.sub(regexes.identifiers_org, '', node_id)
            else:
                print 'Warning: It is safest to use Miriam/identifiers.org identifiers, e.g., http://identifiers.org/mirbase.mature/MIMAT0003389.'
                print ''

            verified_node_id = has_matching_node(current_mapping_graph, node_id)
            # If provided node_id is an identifiers.org IRI, but it doesn't match any nodes, we can
            # try to find nodes by matching the identifier alone (stripping off the namespace).
            if name_or_identifier and (not verified_node_id):
                verified_node_id = has_matching_node(current_mapping_graph, name_or_identifier)

                if not verified_node_id:
                    print 'Warning: No node found matching id "' + node_id + '"'
                    print ''

            # if node is verified to exist in this graph
            if verified_node_id:
                if (verified_node_id != node_id):
                    print 'adding to mappings'
                    print 'verified_node_id'
                    print verified_node_id
                    id_mappings[verified_node_id] = node_id

                '''
                verified_node = current_mapping_graph.node[verified_node_id]
                print ''
                print 'node for selected verified_node_id'
                print verified_node
                '''

                # gets all neighbors, predecesseors and successors.
                neighbor_verified_node_ids = list(nx.all_neighbors(current_mapping_graph, verified_node_id))
                # appears to only get successors.
                #neighbor_verified_node_ids = current_mapping_graph.neighbors(verified_node_id)
                '''
                print ''
                print 'neighbor_verified_node_ids for selected verified_node_id'
                print neighbor_verified_node_ids
                '''

                if not verified_node_id in log_result['results_by_source']:
                    log_result['results_by_source'][verified_node_id] = {}
                log_result['results_by_source'][verified_node_id][version] = len(neighbor_verified_node_ids)

                log_result['total_result_count'] += len(neighbor_verified_node_ids)

                log_result[version + '_result_count'] += len(neighbor_verified_node_ids)

                item_subgraph_node_ids = neighbor_verified_node_ids
                item_subgraph_node_ids.append(verified_node_id)
                datasource_subgraph_node_ids += item_subgraph_node_ids

        if (len(id_mappings) > 0):
            print 'id_mappings'
            print id_mappings
            tmp_subgraph = current_mapping_graph.subgraph(datasource_subgraph_node_ids)
            datasource_subgraph = nx.relabel_nodes(tmp_subgraph, id_mappings, copy=False)
            print 'relabeled'
        else:
            datasource_subgraph = current_mapping_graph.subgraph(datasource_subgraph_node_ids)

        output_graph_name = version + '-subgraph.xgmml'
        output_xgmml_file_path = output_dir + output_graph_name;
        output_xgmml = open(output_xgmml_file_path, 'w')
        networkxgmml.XGMMLWriter(output_xgmml, datasource_subgraph, output_graph_name)
                
        ''' The resulting CSV file should look like this:
        queryid	targetid	score	pvalue	pmid	datasource
        hsa-miR-542-3p	332			20728447	miRTarBase_hsa_r4.4
        '''

        with open(results_file_path, 'a') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for oneedge in datasource_subgraph.edges(data=True):
                print 'oneedge'
                print oneedge
                edge_attributes = oneedge[2]
                if oneedge[0] in node_id_list:
                    row_value = [oneedge[0], oneedge[1]]
                else:
                    row_value = [oneedge[1], oneedge[0]]

                if 'score' in edge_attributes:
                    row_value.append(edge_attributes['score'])
                else:
                    row_value.append('')

                if 'pValue' in edge_attributes:
                    row_value.append(edge_attributes['pValue'])
                else:
                    row_value.append('')

                if 'References (PMID)' in edge_attributes:
                    row_value.append(edge_attributes['References (PMID)'])
                else:
                    row_value.append('')

                if 'datasource' in edge_attributes:
                    row_value.append(edge_attributes['datasource'])
                else:
                    row_value.append('')

                #row_value.append(version)

                print 'row_value'
                print row_value
                csvwriter.writerow(row_value)

    print 'log_result'
    print log_result
    with file(logfile_path, 'w') as f:
        print >>f, '# Queried {} miRNA identifiers.'.format(log_result['query_count'])
        print >>f, '# Skipped {} identifiers.'.format(log_result['skipped_count'])
        print >>f, '# Found {} results.'.format(log_result['total_result_count'])
        header = ['queryid'] + versions
        print >>f, '\t'.join(header)
        for one_node_id in log_result['results_by_source']:
            row = [one_node_id]
            for oneversion in versions:
                if oneversion in log_result['results_by_source'][one_node_id]:
                    row.append(str(log_result['results_by_source'][one_node_id][oneversion]))
                else:
                    row.append('0')
            print >>f, '\t'.join(row)

    return log_result