// grpc_raw.go — JSON-over-gRPC raw byte service registration.
//
// Registers the C7 offer router methods using raw []byte frames so Python
// callers can call with grpc.Channel.unary_unary without generated proto stubs.
// Mirrors the approach used in grpc_client.go of the C5 Go consumer.
//
// gRPC's RegisterService requires HandlerType to be a pointer to an interface.
// We define OfferRouterService as that interface, implemented by OfferRouterServer.
package main

import (
	"context"
	"fmt"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// OfferRouterService is the interface used as HandlerType for gRPC registration.
// OfferRouterServer implements it (all methods are defined on *OfferRouterServer).
type OfferRouterService interface {
	handleTriggerOffer(ctx context.Context, body []byte) ([]byte, error)
	handleAcceptOffer(ctx context.Context, body []byte) ([]byte, error)
	handleRejectOffer(ctx context.Context, body []byte) ([]byte, error)
	handleCancelOffer(ctx context.Context, body []byte) ([]byte, error)
	handleQueryOffer(ctx context.Context, body []byte) ([]byte, error)
	handleHealthCheck(ctx context.Context, body []byte) ([]byte, error)
}

// methodHandler is the signature for handler functions in the raw service.
type methodHandler func(ctx context.Context, body []byte) ([]byte, error)

// buildServiceDesc constructs a gRPC ServiceDesc for JSON-over-gRPC dispatch.
// Each method decodes a raw []byte request, calls the handler, and returns []byte.
func buildServiceDesc(s *OfferRouterServer) grpc.ServiceDesc {
	methods := []struct {
		name    string
		handler methodHandler
	}{
		{"TriggerOffer", s.handleTriggerOffer},
		{"AcceptOffer", s.handleAcceptOffer},
		{"RejectOffer", s.handleRejectOffer},
		{"CancelOffer", s.handleCancelOffer},
		{"QueryOffer", s.handleQueryOffer},
		{"HealthCheck", s.handleHealthCheck},
	}

	grpcMethods := make([]grpc.MethodDesc, 0, len(methods))
	for _, m := range methods {
		m := m // capture loop variable
		grpcMethods = append(grpcMethods, grpc.MethodDesc{
			MethodName: m.name,
			Handler: func(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
				var body []byte
				if err := dec(&body); err != nil {
					return nil, status.Errorf(codes.InvalidArgument, "decode request: %v", err)
				}
				info := &grpc.UnaryServerInfo{
					Server:     srv,
					FullMethod: fmt.Sprintf("/lip.C7OfferRouter/%s", m.name),
				}
				h := func(ctx context.Context, req interface{}) (interface{}, error) {
					b, ok := req.([]byte)
					if !ok {
						return nil, status.Errorf(codes.Internal, "unexpected request type %T", req)
					}
					return m.handler(ctx, b)
				}
				if interceptor != nil {
					return interceptor(ctx, body, info, h)
				}
				return h(ctx, body)
			},
		})
	}

	return grpc.ServiceDesc{
		ServiceName: "lip.C7OfferRouter",
		// HandlerType must be a pointer to an interface type (gRPC requirement).
		HandlerType: (*OfferRouterService)(nil),
		Methods:     grpcMethods,
		Streams:     []grpc.StreamDesc{},
	}
}

// registerRawService registers the C7 offer router service with the gRPC server.
func registerRawService(grpcSrv *grpc.Server, s *OfferRouterServer) {
	desc := buildServiceDesc(s)
	grpcSrv.RegisterService(&desc, s)
}
